
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/error-model.h"
#include "ns3/tcp-socket.h"
#include "ns3/seq-ts-header.h"

#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <algorithm>
#include <iostream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CaseStudy2");

static std::ofstream csv;
static Ptr<FlowMonitor> monitor;
static FlowMonitorHelper flowHelper;
static Ptr<Ipv4FlowClassifier> classifier;

static const double SIM_END = 60.0;
static const double SAMPLE_STEP = 0.5;
static const double LINK_MBPS = 1000.0;
static const uint32_t PAYLOAD_SIZE = 1200;

// UDP-based: giao thuc minh hoa co ACK va truyen lai.
// KHONG phai UDT hoac Aspera thuc te.
class ReliableUdpApp : public Application
{
public:
    ReliableUdpApp()
        : m_sender(false),
          m_running(false),
          m_nextSeq(1),
          m_sent(0),
          m_received(0),
          m_retrans(0),
          m_lastReceived(0),
          m_window(4096)
    {
    }

    void Setup(bool sender, Ipv4Address peer)
    {
        m_sender = sender;
        m_peer = peer;
    }

    uint64_t GetReceivedBytes() const
    {
        return m_received * PAYLOAD_SIZE;
    }

    uint64_t GetReceivedPackets() const
    {
        return m_received;
    }

    uint64_t GetSentPackets() const
    {
        return m_sent;
    }

    uint64_t GetRetransmissions() const
    {
        return m_retrans;
    }

private:
    virtual void StartApplication()
    {
        m_running = true;

        m_socket = Socket::CreateSocket(
            GetNode(),
            UdpSocketFactory::GetTypeId());

        InetSocketAddress local(
            Ipv4Address::GetAny(),
            m_sender ? 9003 : 9002);

        m_socket->Bind(local);
        m_socket->SetRecvCallback(
            MakeCallback(&ReliableUdpApp::HandleRead, this));

        if (m_sender)
        {
            SendNew();
            CheckTimeouts();
        }
    }

    virtual void StopApplication()
    {
        m_running = false;
        m_sendEvent.Cancel();
        m_checkEvent.Cancel();

        if (m_socket)
        {
            m_socket->Close();
        }
    }

    void SendPacket(uint32_t seq, bool retry)
    {
        Ptr<Packet> packet = Create<Packet>(PAYLOAD_SIZE);

        SeqTsHeader header;
        header.SetSeq(seq);
        packet->AddHeader(header);

        m_socket->SendTo(
            packet,
            0,
            InetSocketAddress(m_peer, 9002));

        if (retry)
        {
            m_retrans++;
        }
        else
        {
            m_sent++;
        }

        m_outstanding[seq] = Simulator::Now();
    }

    void SendNew()
    {
        if (!m_running || !m_sender)
        {
            return;
        }

        if (m_outstanding.size() < m_window)
        {
            SendPacket(m_nextSeq++, false);
        }

        // Toc do phat muc tieu ~38 Mbps.
        // Gioi han de mo phong 60 giay chay nhanh.
        m_sendEvent = Simulator::Schedule(
            MicroSeconds(250),
            &ReliableUdpApp::SendNew,
            this);
    }

    void CheckTimeouts()
    {
        if (!m_running || !m_sender)
        {
            return;
        }

        // RTT = 600ms, timeout = 900ms.
        Time now = Simulator::Now();

        for (auto &entry : m_outstanding)
        {
            if (now - entry.second >= MilliSeconds(900))
            {
                Ptr<Packet> packet =
                    Create<Packet>(PAYLOAD_SIZE);

                SeqTsHeader header;
                header.SetSeq(entry.first);
                packet->AddHeader(header);

                m_socket->SendTo(
                    packet,
                    0,
                    InetSocketAddress(m_peer, 9002));

                entry.second = now;
                m_retrans++;
            }
        }

        m_checkEvent = Simulator::Schedule(
            MilliSeconds(100),
            &ReliableUdpApp::CheckTimeouts,
            this);
    }

    void HandleRead(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> packet;

        while ((packet = socket->RecvFrom(from)))
        {
            if (packet->GetSize() == 0)
            {
                continue;
            }

            SeqTsHeader header;

            if (packet->GetSize() < header.GetSerializedSize())
            {
                continue;
            }

            packet->RemoveHeader(header);
            uint32_t seq = header.GetSeq();

            if (m_sender)
            {
                // ACK tu may nhan.
                m_outstanding.erase(seq);
            }
            else
            {
                // Dem moi goi du lieu chi mot lan.
                if (m_seen.insert(seq).second)
                {
                    m_received++;
                }

                // ACK ca goi moi va goi truyen lai.
                Ptr<Packet> ack = Create<Packet>();
                SeqTsHeader ackHeader;
                ackHeader.SetSeq(seq);
                ack->AddHeader(ackHeader);

                socket->SendTo(ack, 0, from);
            }
        }
    }

    bool m_sender;
    bool m_running;
    Ipv4Address m_peer;
    Ptr<Socket> m_socket;

    EventId m_sendEvent;
    EventId m_checkEvent;

    uint32_t m_nextSeq;
    uint64_t m_sent;
    uint64_t m_received;
    uint64_t m_retrans;
    uint64_t m_lastReceived;
    uint32_t m_window;

    std::map<uint32_t, Time> m_outstanding;
    std::set<uint32_t> m_seen;
};

static Ptr<ReliableUdpApp> udpSender;
static Ptr<ReliableUdpApp> udpReceiver;

static std::map<FlowId, uint64_t> lastTcpBytes;
static uint64_t lastUdpBytes = 0;
static double totalTcpBytes = 0;
static double lastTcpMbps = 0;
static double lastUdpMbps = 0;

void SaveResults()
{
    double now = Simulator::Now().GetSeconds();
    double tcpMbps = 0;
    double tcpLatency = 0;
    double tcpLost = 0;
    double tcpTx = 0;
    double tcpRx = 0;

    auto stats = monitor->GetFlowStats();

    for (const auto &item : stats)
    {
        FlowId id = item.first;
        const auto &s = item.second;
        auto tuple = classifier->FindFlow(id);

        if (tuple.protocol != 6 ||
            tuple.destinationPort != 9001)
        {
            continue;
        }

        uint64_t current = s.rxBytes;
        uint64_t previous = lastTcpBytes[id];

        uint64_t delta =
            current >= previous ? current - previous : 0;

        lastTcpBytes[id] = current;

        tcpMbps += delta * 8.0 /
                   SAMPLE_STEP / 1000000.0;

        totalTcpBytes += delta;

        tcpTx += s.txPackets;
        tcpRx += s.rxPackets;
        tcpLost += s.lostPackets;

        if (s.rxPackets > 0)
        {
            tcpLatency =
                s.delaySum.GetSeconds() * 1000.0 /
                s.rxPackets;
        }
    }

    uint64_t udpBytes = udpReceiver->GetReceivedBytes();

    uint64_t udpDelta =
        udpBytes >= lastUdpBytes
        ? udpBytes - lastUdpBytes : 0;

    double udpMbps =
        udpDelta * 8.0 / SAMPLE_STEP / 1000000.0;

    lastUdpBytes = udpBytes;

    double tcpUtil = tcpMbps / LINK_MBPS * 100.0;
    double udpUtil = udpMbps / LINK_MBPS * 100.0;

    // TCP: lost_packets la thong ke FlowMonitor.
    // UDP: retransmissions la so lan truyen lai
    // do ung dung ReliableUdpApp ghi nhan.
    csv << std::fixed << std::setprecision(4);

    csv << now << ",TCP,"
        << tcpMbps << ","
        << tcpUtil << ","
        << tcpLatency << ","
        << tcpTx << ","
        << tcpRx << ","
        << tcpLost << ","
        << 0 << ","
        << totalTcpBytes << "\n";

    csv << now << ",UDP_RELIABLE,"
        << udpMbps << ","
        << udpUtil << ","
        << 0 << ","
        << udpSender->GetSentPackets() << ","
        << udpReceiver->GetReceivedPackets() << ","
        << 0 << ","
        << udpSender->GetRetransmissions() << ","
        << udpBytes << "\n";

    lastTcpMbps = tcpMbps;
    lastUdpMbps = udpMbps;

    if (now + SAMPLE_STEP <= SIM_END)
    {
        Simulator::Schedule(
            Seconds(SAMPLE_STEP), &SaveResults);
    }
}

int main(int argc, char *argv[])
{
    Time::SetResolution(Time::NS);

    // TCP NewReno.
    Config::SetDefault(
    	"ns3::TcpL4Protocol::SocketType",
   	 StringValue("ns3::TcpNewReno"));

    Config::SetDefault(
        "ns3::TcpSocket::SndBufSize",
        UintegerValue(8 * 1024 * 1024));

    Config::SetDefault(
        "ns3::TcpSocket::RcvBufSize",
        UintegerValue(8 * 1024 * 1024));

    // Hai cap node rieng, cung cau hinh mang.
    // TCP va UDP khong canh tranh tren cung link.
    NodeContainer tcpNodes;
    tcpNodes.Create(2);

    NodeContainer udpNodes;
    udpNodes.Create(2);

    PointToPointHelper p2p;

    p2p.SetDeviceAttribute(
        "DataRate", StringValue("1Gbps"));

    // 300ms moi chieu => RTT ~600ms.
    p2p.SetChannelAttribute(
        "Delay", StringValue("300ms"));

    NetDeviceContainer tcpDevices =
        p2p.Install(tcpNodes);

    NetDeviceContainer udpDevices =
        p2p.Install(udpNodes);

    // Nhiem loi goi doc lap cho moi duong truyen.
    Ptr<RateErrorModel> tcpError =
        CreateObject<RateErrorModel>();

    tcpError->SetAttribute(
        "ErrorRate", DoubleValue(0.001));

    tcpError->SetAttribute(
        "ErrorUnit",
        EnumValue(RateErrorModel::ERROR_UNIT_PACKET));

    tcpDevices.Get(1)->SetAttribute(
        "ReceiveErrorModel", PointerValue(tcpError));

    Ptr<RateErrorModel> udpError =
        CreateObject<RateErrorModel>();

    udpError->SetAttribute(
        "ErrorRate", DoubleValue(0.001));

    udpError->SetAttribute(
        "ErrorUnit",
        EnumValue(RateErrorModel::ERROR_UNIT_PACKET));

    udpDevices.Get(1)->SetAttribute(
        "ReceiveErrorModel", PointerValue(udpError));

    InternetStackHelper internet;
    internet.Install(tcpNodes);
    internet.Install(udpNodes);

    Ipv4AddressHelper address;

    address.SetBase(
        "10.2.1.0", "255.255.255.0");

    Ipv4InterfaceContainer tcpInterfaces =
        address.Assign(tcpDevices);

    address.SetBase(
        "10.2.2.0", "255.255.255.0");

    Ipv4InterfaceContainer udpInterfaces =
        address.Assign(udpDevices);

    // ===== TCP NewReno =====
    PacketSinkHelper tcpSink(
        "ns3::TcpSocketFactory",
        InetSocketAddress(
            Ipv4Address::GetAny(), 9001));

    ApplicationContainer tcpSinkApps =
        tcpSink.Install(tcpNodes.Get(1));

    tcpSinkApps.Start(Seconds(0.5));
    tcpSinkApps.Stop(Seconds(61.0));

    BulkSendHelper tcpClient(
        "ns3::TcpSocketFactory",
        InetSocketAddress(
            tcpInterfaces.GetAddress(1), 9001));

    tcpClient.SetAttribute(
        "MaxBytes", UintegerValue(0));

    tcpClient.SetAttribute(
        "SendSize", UintegerValue(1448));

    ApplicationContainer tcpApps =
        tcpClient.Install(tcpNodes.Get(0));

    tcpApps.Start(Seconds(1.0));
    tcpApps.Stop(Seconds(59.5));

    // ===== UDP-based Reliable =====
    udpReceiver = CreateObject<ReliableUdpApp>();
    udpReceiver->Setup(
        false, udpInterfaces.GetAddress(0));

    udpNodes.Get(1)->AddApplication(udpReceiver);

    udpReceiver->SetStartTime(Seconds(0.5));
    udpReceiver->SetStopTime(Seconds(61.0));

    udpSender = CreateObject<ReliableUdpApp>();
    udpSender->Setup(
        true, udpInterfaces.GetAddress(1));

    udpNodes.Get(0)->AddApplication(udpSender);

    udpSender->SetStartTime(Seconds(1.0));
    udpSender->SetStopTime(Seconds(59.5));

    // ===== FlowMonitor =====
    monitor = flowHelper.InstallAll();

    classifier =
        DynamicCast<Ipv4FlowClassifier>(
            flowHelper.GetClassifier());

    csv.open("results/case2.csv");

    if (!csv.is_open())
    {
        std::cerr
            << "Khong mo duoc results/case2.csv\n";
        return 1;
    }

    csv << "time,protocol,throughput_mbps,"
           "utilization_percent,latency_ms,"
           "tx_packets,rx_packets,lost_packets,"
           "retransmissions,received_bytes\n";

    Simulator::Schedule(
        Seconds(1.5), &SaveResults);

    Simulator::Stop(Seconds(60.5));
    Simulator::Run();

    monitor->CheckForLostPackets();

    monitor->SerializeToXmlFile(
        "results/case2_flowmon.xml",
        true, true);

    csv.close();

    std::cout
        << "Da xuat results/case2.csv\n"
        << "Da xuat results/case2_flowmon.xml\n"
        << "Link: 1000 Mbps\n"
        << "RTT ly thuyet: 600 ms\n"
        << "Packet error rate: 0.001\n"
        << "UDP retransmissions: "
        << udpSender->GetRetransmissions()
        << std::endl;

    Simulator::Destroy();
    return 0;
}
