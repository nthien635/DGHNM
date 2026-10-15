
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/error-model.h"
#include "ns3/tcp-header.h"
#include "ns3/ipv4-header.h"

#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <iostream>
#include <cstdint>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CaseStudy1");

// Bien dung chung
static std::ofstream csv;
static Ptr<FlowMonitor> monitor;
static FlowMonitorHelper flowHelper;
static Ptr<Ipv4FlowClassifier> classifier;

static std::map<FlowId, uint64_t> lastRxBytes;
static std::set<uint32_t> tcpSequences;

static uint32_t tcpRetransmissions = 0;

// Theo doi cac TCP sequence number duoc gui lai
// Day la phep dem don gian de uoc luong retransmission
void TrackTcpTx(Ptr<const Packet> packet,
                Ptr<Ipv4> ipv4,
                uint32_t interface)
{
    Ptr<Packet> copy = packet->Copy();

    Ipv4Header ipHeader;

    if (copy->PeekHeader(ipHeader) == 0)
        return;

    if (ipHeader.GetProtocol() != 6)
        return;

    copy->RemoveHeader(ipHeader);

    TcpHeader tcpHeader;

    if (copy->PeekHeader(tcpHeader) == 0)
        return;

    uint32_t headerSize =
        tcpHeader.GetSerializedSize();

    if (copy->GetSize() <= headerSize)
        return;

    uint32_t seq =
        tcpHeader.GetSequenceNumber().GetValue();

    if (!tcpSequences.insert(seq).second)
    {
        tcpRetransmissions++;
    }
}

// Ham thong ke so goi UDP
void GetUdpStats(uint64_t &udpTx,
                 uint64_t &udpRx)
{
    udpTx = 0;
    udpRx = 0;

    auto stats = monitor->GetFlowStats();

    for (const auto &item : stats)
    {
        auto tuple =
            classifier->FindFlow(item.first);

        if (tuple.protocol == 17 &&
            tuple.destinationPort == 9000)
        {
            udpTx += item.second.txPackets;
            udpRx += item.second.rxPackets;
        }
    }
}

// Ghi du lieu vao CSV moi 0.5 giay
void SaveResults()
{
    monitor->CheckForLostPackets();

    auto stats = monitor->GetFlowStats();

    // 1. Thong ke UDP Packet Loss
    uint64_t udpTransmitted = 0;
    uint64_t udpReceived = 0;

    GetUdpStats(udpTransmitted, udpReceived);

    uint64_t udpNotReceived =
        udpTransmitted > udpReceived
        ? udpTransmitted - udpReceived
        : 0;

    double udpLossPercent =
        udpTransmitted > 0
        ? 100.0 * udpNotReceived /
          static_cast<double>(udpTransmitted)
        : 0.0;

    // 2. Thong ke TCP va UDP
    for (const auto &item : stats)
    {
        FlowId id = item.first;
        const auto &s = item.second;

        auto tuple = classifier->FindFlow(id);

        if (tuple.destinationPort != 9000 &&
            tuple.destinationPort != 9001)
        {
            continue;
        }

        std::string protocol =
            tuple.destinationPort == 9000
            ? "UDP" : "TCP";

        // 3. Tinh throughput moi 0.5 giay
        uint64_t previous = lastRxBytes[id];
        uint64_t current = s.rxBytes;

        double throughput =
            (current - previous) * 8.0 /
            0.5 / 1000000.0;

        lastRxBytes[id] = current;

        // 4. Tinh latency trung binh
        double latency = 0.0;

        if (s.rxPackets > 0)
        {
            latency =
                s.delaySum.GetSeconds() *
                1000.0 / s.rxPackets;
        }

        // 5. Tinh jitter trung binh
        double jitter = 0.0;

        if (s.rxPackets > 1)
        {
            jitter =
                s.jitterSum.GetSeconds() *
                1000.0 / (s.rxPackets - 1);
        }

        // 6. Ghi du lieu ra CSV
        csv << std::fixed
            << std::setprecision(3)
            << Simulator::Now().GetSeconds() << ","
            << protocol << ","
            << s.txPackets << ","
            << s.rxPackets << ","
            << s.lostPackets << ","
            << latency << ","
            << jitter << ","
            << throughput << ","
            << udpLossPercent << ","
            << tcpRetransmissions << "\n";
    }

    // Lap lai moi 0.5 giay
    if (Simulator::Now().GetSeconds() < 20.0)
    {
        Simulator::Schedule(
            Seconds(0.5), &SaveResults);
    }
}

int main(int argc, char *argv[])
{
    Time::SetResolution(Time::NS);

    // ====================================
    // 1. TAO HAI NODE
    // ====================================
    NodeContainer nodes;
    nodes.Create(2);

    // ====================================
    // 2. CAU HINH DUONG TRUYEN
    // ====================================
    PointToPointHelper p2p;

    p2p.SetDeviceAttribute(
        "DataRate", StringValue("10Mbps"));

    p2p.SetChannelAttribute(
        "Delay", StringValue("25ms"));

    NetDeviceContainer devices =
        p2p.Install(nodes);

    // ====================================
    // 3. CAU HINH PACKET LOSS 2%
    // ====================================
    Ptr<RateErrorModel> errorModel =
        CreateObject<RateErrorModel>();

    errorModel->SetAttribute(
        "ErrorRate", DoubleValue(0.02));

    errorModel->SetAttribute(
        "ErrorUnit",
        EnumValue(
            RateErrorModel::ERROR_UNIT_PACKET));

    devices.Get(1)->SetAttribute(
        "ReceiveErrorModel",
        PointerValue(errorModel));

    // ====================================
    // 4. CAU HINH IP
    // ====================================
    InternetStackHelper internet;
    internet.Install(nodes);

    Ipv4AddressHelper address;

    address.SetBase(
        "10.1.1.0", "255.255.255.0");

    Ipv4InterfaceContainer interfaces =
        address.Assign(devices);

    // ====================================
    // 5. UDP SERVER
    // ====================================
    uint16_t udpPort = 9000;

    UdpServerHelper udpServer(udpPort);

    ApplicationContainer udpServerApps =
        udpServer.Install(nodes.Get(1));

    udpServerApps.Start(Seconds(0.5));
    udpServerApps.Stop(Seconds(20.0));

    // ====================================
    // 6. UDP CLIENT
    // ====================================
    UdpClientHelper udpClient(
        interfaces.GetAddress(1),
        udpPort);

    udpClient.SetAttribute(
        "MaxPackets",
        UintegerValue(100000));

    udpClient.SetAttribute(
        "Interval",
        TimeValue(MilliSeconds(10)));

    udpClient.SetAttribute(
        "PacketSize",
        UintegerValue(1400));

    ApplicationContainer udpApps =
        udpClient.Install(nodes.Get(0));

    udpApps.Start(Seconds(1.0));
    udpApps.Stop(Seconds(19.5));

    // ====================================
    // 7. TCP SERVER
    // ====================================
    uint16_t tcpPort = 9001;

    Address sinkAddress(
        InetSocketAddress(
            Ipv4Address::GetAny(),
            tcpPort));

    PacketSinkHelper tcpSink(
        "ns3::TcpSocketFactory",
        sinkAddress);

    ApplicationContainer sinkApps =
        tcpSink.Install(nodes.Get(1));

    sinkApps.Start(Seconds(0.5));
    sinkApps.Stop(Seconds(20.0));

    // ====================================
    // 8. TCP CLIENT
    // ====================================
    OnOffHelper tcpClient(
        "ns3::TcpSocketFactory",
        InetSocketAddress(
            interfaces.GetAddress(1),
            tcpPort));

    tcpClient.SetAttribute(
        "DataRate",
        StringValue("2Mbps"));

    tcpClient.SetAttribute(
        "PacketSize",
        UintegerValue(1400));

    tcpClient.SetAttribute(
        "OnTime",
        StringValue(
            "ns3::ConstantRandomVariable[Constant=1]"));

    tcpClient.SetAttribute(
        "OffTime",
        StringValue(
            "ns3::ConstantRandomVariable[Constant=0]"));

    ApplicationContainer tcpApps =
        tcpClient.Install(nodes.Get(0));

    tcpApps.Start(Seconds(1.0));
    tcpApps.Stop(Seconds(19.5));

    // ====================================
    // 9. THEO DOI TCP RETRANSMISSION
    // ====================================
    Config::ConnectWithoutContext(
        "/NodeList/0/$ns3::Ipv4L3Protocol/Tx",
        MakeCallback(&TrackTcpTx));

    // ====================================
    // 10. CAI FLOWMONITOR
    // ====================================
    monitor = flowHelper.InstallAll();

    classifier =
        DynamicCast<Ipv4FlowClassifier>(
            flowHelper.GetClassifier());

    // ====================================
    // 11. TAO FILE CSV
    // ====================================
    csv.open("results/case1.csv");

    if (!csv.is_open())
    {
        std::cerr
            << "Khong mo duoc results/case1.csv"
            << std::endl;

        return 1;
    }

    csv << "time,protocol,tx_packets,rx_packets,"
           "lost_packets,latency_ms,jitter_ms,"
           "throughput_mbps,udp_loss_percent,"
           "tcp_retransmissions\n";

    Simulator::Schedule(
        Seconds(1.5), &SaveResults);

    // ====================================
    // 12. CHAY MO PHONG
    // ====================================
    Simulator::Stop(Seconds(20.5));
    Simulator::Run();

    monitor->CheckForLostPackets();

    // ====================================
    // 13. THONG KE UDP CUOI CUNG
    // ====================================
    uint64_t totalUdpTx = 0;
    uint64_t totalUdpRx = 0;

    GetUdpStats(totalUdpTx, totalUdpRx);

    uint64_t totalUdpNotReceived =
        totalUdpTx > totalUdpRx
        ? totalUdpTx - totalUdpRx
        : 0;

    double finalUdpLoss =
        totalUdpTx > 0
        ? 100.0 * totalUdpNotReceived /
          static_cast<double>(totalUdpTx)
        : 0.0;

    std::cout
        << "\n===== THONG KE UDP =====\n";

    std::cout
        << "UDP Sent: "
        << totalUdpTx << "\n";

    std::cout
        << "UDP Received: "
        << totalUdpRx << "\n";

    std::cout
        << "UDP Not Received: "
        << totalUdpNotReceived << "\n";

    std::cout
        << "UDP Loss Estimate: "
        << std::fixed
        << std::setprecision(2)
        << finalUdpLoss << "%\n";

    std::cout
        << "TCP Retransmissions (estimate): "
        << tcpRetransmissions << "\n";

    std::cout
        << "========================\n";

    // ====================================
    // 14. XUAT XML
    // ====================================
    monitor->SerializeToXmlFile(
        "results/case1_flowmon.xml",
        true,
        true);

    csv.close();

    std::cout
        << "Da xuat results/case1.csv"
        << std::endl;

    Simulator::Destroy();

    return 0;
}
