
// CASE STUDY 3 - NS-3.34
// TCP ordered stream vs UDP reliable independent streams
// Educational QUIC-like model, NOT real HTTP/3/QUIC.

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/error-model.h"

#include <fstream>
#include <iomanip>
#include <vector>
#include <algorithm>
#include <cstdint>

using namespace ns3;

static const uint32_t NSTREAMS = 6;
static const uint32_t NPACKETS = 128;
static const uint32_t PAYLOAD = 1200;
static const uint32_t WINDOW = 24;
static const uint32_t TOTAL = NSTREAMS * NPACKETS * PAYLOAD;

static const double START = 1.0;
static const double STOP = 15.0;
static const double TICK = 0.25;

static Ptr<Socket> udpTx[NSTREAMS], udpRx;
static Ipv4Address udpDestination;
static Ptr<PacketSink> tcpSink;

static std::vector<bool> acked[NSTREAMS];
static std::vector<bool> received[NSTREAMS];
static std::vector<double> lastSent[NSTREAMS];

static uint32_t nextSeq[NSTREAMS] = {0};
static uint32_t inFlight[NSTREAMS] = {0};
static uint32_t ackCount[NSTREAMS] = {0};

static uint64_t udpBytes = 0;
static uint64_t tcpLast = 0;
static uint64_t udpLast = 0;
static uint64_t udpTxCount = 0;
static uint64_t udpRetrans = 0;
static uint64_t udpUnique = 0;

static double tcpDone[NSTREAMS] = {0};
static double udpDone[NSTREAMS] = {0};

static std::ofstream samples, streams;

static void WriteU32(uint8_t *p, uint32_t n)
{
    p[0] = uint8_t(n >> 24);
    p[1] = uint8_t(n >> 16);
    p[2] = uint8_t(n >> 8);
    p[3] = uint8_t(n);
}

static uint32_t ReadU32(const uint8_t *p)
{
    return (uint32_t(p[0]) << 24) |
           (uint32_t(p[1]) << 16) |
           (uint32_t(p[2]) << 8) |
           uint32_t(p[3]);
}

static void SendOne(uint32_t s, uint32_t q, bool retry)
{
    if (acked[s][q]) return;

    uint8_t bytes[8 + PAYLOAD] = {0};

    WriteU32(bytes, s);
    WriteU32(bytes + 4, q);

    udpTx[s]->SendTo(
        Create<Packet>(bytes, sizeof(bytes)),
        0,
        InetSocketAddress(udpDestination, 9000)
    );

    lastSent[s][q] = Simulator::Now().GetSeconds();

    ++udpTxCount;

    if (retry) ++udpRetrans;
}

static void FillWindow(uint32_t s)
{
    while (inFlight[s] < WINDOW &&
           nextSeq[s] < NPACKETS)
    {
        uint32_t q = nextSeq[s]++;

        ++inFlight[s];

        SendOne(s, q, false);
    }
}

static void OnAck(Ptr<Socket> sock)
{
    Ptr<Packet> p;
    Address from;

    while ((p = sock->RecvFrom(from)))
    {
        if (p->GetSize() < 8) continue;

        uint8_t b[8];
        p->CopyData(b, 8);

        uint32_t s = ReadU32(b);
        uint32_t q = ReadU32(b + 4);

        if (s >= NSTREAMS ||
            q >= NPACKETS ||
            acked[s][q])
            continue;

        acked[s][q] = true;
        ++ackCount[s];

        if (inFlight[s]) --inFlight[s];

        if (ackCount[s] == NPACKETS &&
            udpDone[s] == 0)
        {
            udpDone[s] =
                Simulator::Now().GetSeconds() - START;
        }

        FillWindow(s);
    }
}

static void OnUdpReceive(Ptr<Socket> sock)
{
    Ptr<Packet> p;
    Address from;

    while ((p = sock->RecvFrom(from)))
    {
        if (p->GetSize() < 8) continue;

        uint8_t b[8];
        p->CopyData(b, 8);

        uint32_t s = ReadU32(b);
        uint32_t q = ReadU32(b + 4);

        if (s >= NSTREAMS || q >= NPACKETS)
            continue;

        if (!received[s][q])
        {
            received[s][q] = true;
            ++udpUnique;
            udpBytes += PAYLOAD;
        }

        // ACK for new and duplicate packets
        sock->SendTo(Create<Packet>(b, 8), 0, from);
    }
}

static void RetransmissionTimer()
{
    double now = Simulator::Now().GetSeconds();

    for (uint32_t s = 0; s < NSTREAMS; ++s)
    {
        for (uint32_t q = 0; q < nextSeq[s]; ++q)
        {
            if (!acked[s][q] &&
                now - lastSent[s][q] >= 0.35)
            {
                SendOne(s, q, true);
            }
        }
    }

    if (now < STOP - 0.1)
    {
        Simulator::Schedule(
            MilliSeconds(50),
            &RetransmissionTimer
        );
    }
}

static void Sample()
{
    double now = Simulator::Now().GetSeconds();

    uint64_t tcpBytes = tcpSink->GetTotalRx();

    if (tcpBytes > TOTAL)
        tcpBytes = TOTAL;

    for (uint32_t s = 0; s < NSTREAMS; ++s)
    {
        if (tcpDone[s] == 0 &&
            tcpBytes >=
                uint64_t(s + 1) * NPACKETS * PAYLOAD)
        {
            tcpDone[s] = now - START;
        }
    }

    double tcpRate =
        8.0 * double(tcpBytes - tcpLast) /
        TICK / 1e6;

    double udpRate =
        8.0 * double(udpBytes - udpLast) /
        TICK / 1e6;

    tcpLast = tcpBytes;
    udpLast = udpBytes;

    // Retry ratio, not physical packet loss
    double retryRatio = udpTxCount
        ? 100.0 * double(udpRetrans) /
          double(udpTxCount)
        : 0.0;

    samples << std::fixed
            << std::setprecision(4);

    samples << now
            << ",TCP,"
            << tcpRate << ","
            << tcpBytes
            << ",0,50,0\n";

    samples << now
            << ",UDP-reliable,"
            << udpRate << ","
            << udpBytes << ","
            << retryRatio
            << ",50,"
            << udpRetrans << "\n";

    if (now + TICK <= STOP + 1e-6)
    {
        Simulator::Schedule(
            Seconds(TICK), &Sample
        );
    }
}

int main(int argc, char **argv)
{
    double errorRate = 0.02;

    CommandLine cmd;

    cmd.AddValue(
        "errorRate",
        "Forward packet error probability",
        errorRate
    );

    cmd.Parse(argc, argv);

    Time::SetResolution(Time::NS);

    // Independent networks with same settings
    NodeContainer tcpNodes, udpNodes;

    tcpNodes.Create(2);
    udpNodes.Create(2);

    PointToPointHelper p2p;

    p2p.SetDeviceAttribute(
        "DataRate", StringValue("10Mbps")
    );

    p2p.SetChannelAttribute(
        "Delay", StringValue("50ms")
    );

    NetDeviceContainer tcpDevices =
        p2p.Install(tcpNodes);

    NetDeviceContainer udpDevices =
        p2p.Install(udpNodes);

    Ptr<RateErrorModel> tcpError =
        CreateObject<RateErrorModel>();

    tcpError->SetAttribute(
        "ErrorRate", DoubleValue(errorRate)
    );

    tcpError->SetAttribute(
        "ErrorUnit",
        EnumValue(RateErrorModel::ERROR_UNIT_PACKET)
    );

    tcpDevices.Get(1)->SetAttribute(
        "ReceiveErrorModel",
        PointerValue(tcpError)
    );

    Ptr<RateErrorModel> udpError =
        CreateObject<RateErrorModel>();

    udpError->SetAttribute(
        "ErrorRate", DoubleValue(errorRate)
    );

    udpError->SetAttribute(
        "ErrorUnit",
        EnumValue(RateErrorModel::ERROR_UNIT_PACKET)
    );

    udpDevices.Get(1)->SetAttribute(
        "ReceiveErrorModel",
        PointerValue(udpError)
    );

    InternetStackHelper internet;

    internet.Install(tcpNodes);
    internet.Install(udpNodes);

    Ipv4AddressHelper addr;

    addr.SetBase(
        "10.3.1.0", "255.255.255.0"
    );

    Ipv4InterfaceContainer tcpIf =
        addr.Assign(tcpDevices);

    addr.SetBase(
        "10.3.2.0", "255.255.255.0"
    );

    Ipv4InterfaceContainer udpIf =
        addr.Assign(udpDevices);

    udpDestination = udpIf.GetAddress(1);

    // TCP: one ordered byte stream
    PacketSinkHelper sinkHelper(
        "ns3::TcpSocketFactory",
        InetSocketAddress(
            Ipv4Address::GetAny(), 8001
        )
    );

    ApplicationContainer sinkApps =
        sinkHelper.Install(tcpNodes.Get(1));

    sinkApps.Start(Seconds(0.2));
    sinkApps.Stop(Seconds(STOP + 0.1));

    tcpSink =
        DynamicCast<PacketSink>(sinkApps.Get(0));

    BulkSendHelper bulk(
        "ns3::TcpSocketFactory",
        InetSocketAddress(
            tcpIf.GetAddress(1), 8001
        )
    );

    bulk.SetAttribute(
        "MaxBytes", UintegerValue(TOTAL)
    );

    bulk.SetAttribute(
        "SendSize", UintegerValue(PAYLOAD)
    );

    ApplicationContainer sendApps =
        bulk.Install(tcpNodes.Get(0));

    sendApps.Start(Seconds(START));
    sendApps.Stop(Seconds(STOP));

    // UDP: six independent reliable streams
    udpRx = Socket::CreateSocket(
        udpNodes.Get(1),
        UdpSocketFactory::GetTypeId()
    );

    udpRx->Bind(
        InetSocketAddress(
            Ipv4Address::GetAny(), 9000
        )
    );

    udpRx->SetRecvCallback(
        MakeCallback(&OnUdpReceive)
    );

    for (uint32_t s = 0; s < NSTREAMS; ++s)
    {
        acked[s].assign(NPACKETS, false);
        received[s].assign(NPACKETS, false);
        lastSent[s].assign(NPACKETS, 0.0);

        udpTx[s] = Socket::CreateSocket(
            udpNodes.Get(0),
            UdpSocketFactory::GetTypeId()
        );

        udpTx[s]->Bind();

        udpTx[s]->SetRecvCallback(
            MakeCallback(&OnAck)
        );
    }

    FlowMonitorHelper fm;

    Ptr<FlowMonitor> mon = fm.InstallAll();

    samples.open("results/case3.csv");
    streams.open("results/case3_streams.csv");

    if (!samples || !streams)
    {
        std::cerr
            << "Create results directory first\n";
        return 1;
    }

    samples
        << "time,protocol,throughput_mbps,"
        << "received_bytes,packet_loss_percent,"
        << "latency_ms,retransmissions\n";

    streams
        << "stream,tcp_completion_s,"
        << "udp_completion_s\n";

    for (uint32_t s = 0; s < NSTREAMS; ++s)
    {
        Simulator::Schedule(
            Seconds(START + 0.01),
            &FillWindow,
            s
        );
    }

    Simulator::Schedule(
        Seconds(START + 0.1),
        &RetransmissionTimer
    );

    Simulator::Schedule(
        Seconds(START + TICK),
        &Sample
    );

    Simulator::Stop(
        Seconds(STOP + 0.2)
    );

    Simulator::Run();

    for (uint32_t s = 0; s < NSTREAMS; ++s)
    {
        streams
            << (s + 1) << ","
            << tcpDone[s] << ","
            << udpDone[s] << "\n";
    }

    mon->CheckForLostPackets();

    mon->SerializeToXmlFile(
        "results/case3_flowmon.xml",
        true, true
    );

    samples.close();
    streams.close();

    std::cout
        << "Created results/case3.csv, "
        << "case3_streams.csv, "
        << "case3_flowmon.xml\n";

    std::cout
        << "TCP bytes: "
        << tcpSink->GetTotalRx()
        << " / " << TOTAL << "\n";

    std::cout
        << "UDP unique packets: "
        << udpUnique
        << " / "
        << NSTREAMS * NPACKETS
        << "; retransmission attempts: "
        << udpRetrans << "\n";

    Simulator::Destroy();

    return 0;
}
