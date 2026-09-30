import random
import statistics
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

# THÊM THƯ VIỆN EXCEL
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


# =====================================================
# CẤU HÌNH MÔ PHỎNG
# =====================================================

PACKET_LOSS = 0.02          # Tỷ lệ mất gói 2%
BASE_LATENCY = 50           # Độ trễ cơ bản (ms)
NETWORK_JITTER = 10         # Dao động độ trễ (ms)
TCP_RETRANSMISSION = 100    # Thời gian truyền lại TCP (ms)

PACKET_SIZE = 1400          # Kích thước mỗi gói (byte)
PACKETS_PER_INTERVAL = 100  # Số gói mỗi lần mô phỏng

INTERVAL = 500              # 500 ms = 0.5 giây
MAX_POINTS = 30             # Hiển thị 30 điểm gần nhất


# =====================================================
# TẠO FILE EXCEL
# =====================================================

EXCEL_FILE = "ket_qua_mo_phong.xlsx"

workbook = Workbook()
worksheet = workbook.active
worksheet.title = "Ket qua mo phong"

# Tiêu đề các cột
headers = [
    "Thời gian (giây)",

    "UDP - Gói gửi",
    "UDP - Gói nhận",
    "UDP - Gói mất",
    "UDP - Tỷ lệ mất (%)",
    "UDP - Độ trễ (ms)",
    "UDP - Dao động trễ (ms)",
    "UDP - Thông lượng (Mbps)",

    "TCP - Gói gửi",
    "TCP - Gói nhận",
    "TCP - Gói truyền lại",
    "TCP - Độ trễ (ms)",
    "TCP - Dao động trễ (ms)",
    "TCP - Thông lượng (Mbps)"
]

worksheet.append(headers)

# Định dạng dòng tiêu đề
for cell in worksheet[1]:
    cell.font = Font(bold=True)
    cell.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )

# Điều chỉnh độ rộng cột
column_widths = {
    "A": 18,
    "B": 16,
    "C": 16,
    "D": 16,
    "E": 20,
    "F": 20,
    "G": 25,
    "H": 25,
    "I": 16,
    "J": 16,
    "K": 22,
    "L": 20,
    "M": 25,
    "N": 25
}

for column, width in column_widths.items():
    worksheet.column_dimensions[column].width = width

# Lưu file ngay từ đầu
workbook.save(EXCEL_FILE)


# =====================================================
# DỮ LIỆU ĐỒ THỊ REALTIME
# =====================================================

times = deque(maxlen=MAX_POINTS)

udp_latency_data = deque(maxlen=MAX_POINTS)
tcp_latency_data = deque(maxlen=MAX_POINTS)

udp_jitter_data = deque(maxlen=MAX_POINTS)
tcp_jitter_data = deque(maxlen=MAX_POINTS)

udp_throughput_data = deque(maxlen=MAX_POINTS)
tcp_throughput_data = deque(maxlen=MAX_POINTS)

udp_loss_data = deque(maxlen=MAX_POINTS)
tcp_retransmission_data = deque(maxlen=MAX_POINTS)

current_time = 0


# =====================================================
# MÔ PHỎNG UDP
# =====================================================

def simulate_udp():

    latencies = []
    lost = 0

    # Gửi 100 gói UDP
    for i in range(PACKETS_PER_INTERVAL):

        # Mô phỏng mất gói 2%
        if random.random() < PACKET_LOSS:
            lost += 1
            continue

        # Tạo độ trễ ngẫu nhiên
        latency = BASE_LATENCY + random.uniform(
            -NETWORK_JITTER,
            NETWORK_JITTER
        )

        latencies.append(latency)

    # Số gói nhận được
    received = PACKETS_PER_INTERVAL - lost

    # Độ trễ trung bình
    if len(latencies) > 0:
        avg_latency = statistics.mean(latencies)
    else:
        avg_latency = 0

    # Độ dao động trễ
    if len(latencies) > 1:
        jitter = statistics.stdev(latencies)
    else:
        jitter = 0

    # Tỷ lệ mất gói
    loss_percent = (
        lost / PACKETS_PER_INTERVAL
    ) * 100

    # Thời gian mỗi lần cập nhật
    interval_seconds = INTERVAL / 1000

    # Tính thông lượng Mbps
    throughput = (
        received
        * PACKET_SIZE
        * 8
    ) / interval_seconds / 1_000_000

    return {
        "sent": PACKETS_PER_INTERVAL,
        "received": received,
        "lost": lost,
        "loss_percent": loss_percent,
        "latency": avg_latency,
        "jitter": jitter,
        "throughput": throughput
    }


# =====================================================
# MÔ PHỎNG TCP
# =====================================================

def simulate_tcp():

    latencies = []
    retransmissions = 0

    # Gửi 100 gói TCP
    for i in range(PACKETS_PER_INTERVAL):

        latency = BASE_LATENCY + random.uniform(
            -NETWORK_JITTER,
            NETWORK_JITTER
        )

        # Mô phỏng mất gói
        if random.random() < PACKET_LOSS:

            # TCP phải truyền lại
            retransmissions += 1

            # Tăng độ trễ
            latency += TCP_RETRANSMISSION

        latencies.append(latency)

    # TCP cuối cùng nhận đủ dữ liệu
    received = PACKETS_PER_INTERVAL

    # Độ trễ trung bình
    avg_latency = statistics.mean(latencies)

    # Độ dao động trễ
    if len(latencies) > 1:
        jitter = statistics.stdev(latencies)
    else:
        jitter = 0

    # Thời gian một chu kỳ
    interval_seconds = INTERVAL / 1000

    # Thời gian phát sinh do truyền lại
    retransmission_delay = (
        retransmissions
        * TCP_RETRANSMISSION
    ) / 1000

    # Tổng thời gian hiệu dụng
    effective_time = (
        interval_seconds
        + retransmission_delay
    )

    # Tính thông lượng
    throughput = (
        received
        * PACKET_SIZE
        * 8
    ) / effective_time / 1_000_000

    return {
        "sent": PACKETS_PER_INTERVAL,
        "received": received,
        "retransmissions": retransmissions,
        "latency": avg_latency,
        "jitter": jitter,
        "throughput": throughput
    }


# =====================================================
# TẠO CỬA SỔ ĐỒ THỊ
# =====================================================

fig, axes = plt.subplots(
    2,
    2,
    figsize=(12, 8)
)

fig.suptitle(
    "SO SÁNH TCP VÀ UDP - MÔ PHỎNG TRUYỀN PHÁT VIDEO",
    fontsize=14
)


# =====================================================
# BIỂU ĐỒ 1 - ĐỘ TRỄ
# =====================================================

ax_latency = axes[0][0]

udp_latency_line, = ax_latency.plot(
    [],
    [],
    label="UDP"
)

tcp_latency_line, = ax_latency.plot(
    [],
    [],
    label="TCP"
)

ax_latency.set_title("Độ trễ")
ax_latency.set_xlabel("Thời gian (giây)")
ax_latency.set_ylabel("Độ trễ (ms)")
ax_latency.set_ylim(0, 180)
ax_latency.grid(True)
ax_latency.legend()


# =====================================================
# BIỂU ĐỒ 2 - ĐỘ DAO ĐỘNG TRỄ
# =====================================================

ax_jitter = axes[0][1]

udp_jitter_line, = ax_jitter.plot(
    [],
    [],
    label="UDP"
)

tcp_jitter_line, = ax_jitter.plot(
    [],
    [],
    label="TCP"
)

ax_jitter.set_title("Độ dao động trễ")
ax_jitter.set_xlabel("Thời gian (giây)")
ax_jitter.set_ylabel("Độ dao động trễ (ms)")
ax_jitter.set_ylim(0, 60)
ax_jitter.grid(True)
ax_jitter.legend()


# =====================================================
# BIỂU ĐỒ 3 - THÔNG LƯỢNG
# =====================================================

ax_throughput = axes[1][0]

udp_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="UDP"
)

tcp_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="TCP"
)

ax_throughput.set_title("Thông lượng")
ax_throughput.set_xlabel("Thời gian (giây)")
ax_throughput.set_ylabel("Thông lượng (Mbps)")
ax_throughput.set_ylim(0, 3)
ax_throughput.grid(True)
ax_throughput.legend()


# =====================================================
# BIỂU ĐỒ 4 - MẤT GÓI / TRUYỀN LẠI
# =====================================================

ax_loss = axes[1][1]

udp_loss_line, = ax_loss.plot(
    [],
    [],
    label="UDP - Tỷ lệ mất gói (%)"
)

tcp_retrans_line, = ax_loss.plot(
    [],
    [],
    label="TCP - Số gói truyền lại"
)

ax_loss.set_title("Mất gói và truyền lại")
ax_loss.set_xlabel("Thời gian (giây)")
ax_loss.set_ylabel("Tỷ lệ (%) / Số gói")
ax_loss.set_ylim(0, 10)
ax_loss.grid(True)
ax_loss.legend()


# =====================================================
# HÀM CẬP NHẬT REALTIME
# =====================================================

def update(frame):

    global current_time

    # Tăng thời gian thêm 0.5 giây
    current_time += INTERVAL / 1000

    # Chạy UDP
    udp = simulate_udp()

    # Chạy TCP
    tcp = simulate_tcp()


    # =================================================
    # LƯU DỮ LIỆU ĐỒ THỊ
    # =================================================

    times.append(current_time)

    udp_latency_data.append(
        udp["latency"]
    )

    tcp_latency_data.append(
        tcp["latency"]
    )

    udp_jitter_data.append(
        udp["jitter"]
    )

    tcp_jitter_data.append(
        tcp["jitter"]
    )

    udp_throughput_data.append(
        udp["throughput"]
    )

    tcp_throughput_data.append(
        tcp["throughput"]
    )

    udp_loss_data.append(
        udp["loss_percent"]
    )

    tcp_retransmission_data.append(
        tcp["retransmissions"]
    )


    # =================================================
    # GHI DỮ LIỆU VÀO EXCEL
    # =================================================

    worksheet.append([
        round(current_time, 1),

        udp["sent"],
        udp["received"],
        udp["lost"],
        round(udp["loss_percent"], 2),
        round(udp["latency"], 2),
        round(udp["jitter"], 2),
        round(udp["throughput"], 3),

        tcp["sent"],
        tcp["received"],
        tcp["retransmissions"],
        round(tcp["latency"], 2),
        round(tcp["jitter"], 2),
        round(tcp["throughput"], 3)
    ])

    # Lưu file sau mỗi lần cập nhật
    workbook.save(EXCEL_FILE)


    # =================================================
    # CẬP NHẬT BIỂU ĐỒ ĐỘ TRỄ
    # =================================================

    udp_latency_line.set_data(
        list(times),
        list(udp_latency_data)
    )

    tcp_latency_line.set_data(
        list(times),
        list(tcp_latency_data)
    )


    # =================================================
    # CẬP NHẬT BIỂU ĐỒ DAO ĐỘNG TRỄ
    # =================================================

    udp_jitter_line.set_data(
        list(times),
        list(udp_jitter_data)
    )

    tcp_jitter_line.set_data(
        list(times),
        list(tcp_jitter_data)
    )


    # =================================================
    # CẬP NHẬT BIỂU ĐỒ THÔNG LƯỢNG
    # =================================================

    udp_throughput_line.set_data(
        list(times),
        list(udp_throughput_data)
    )

    tcp_throughput_line.set_data(
        list(times),
        list(tcp_throughput_data)
    )


    # =================================================
    # CẬP NHẬT BIỂU ĐỒ MẤT GÓI
    # =================================================

    udp_loss_line.set_data(
        list(times),
        list(udp_loss_data)
    )

    tcp_retrans_line.set_data(
        list(times),
        list(tcp_retransmission_data)
    )


    # =================================================
    # CHO TRỤC X CHẠY THEO THỜI GIAN
    # =================================================

    if current_time > 15:
        xmin = current_time - 15
        xmax = current_time
    else:
        xmin = 0
        xmax = 15

    ax_latency.set_xlim(
        xmin,
        xmax
    )

    ax_jitter.set_xlim(
        xmin,
        xmax
    )

    ax_throughput.set_xlim(
        xmin,
        xmax
    )

    ax_loss.set_xlim(
        xmin,
        xmax
    )


    # =================================================
    # IN KẾT QUẢ CHI TIẾT RA TERMINAL
    # =================================================

    print(
        "\n========== THỜI GIAN: %.1f giây =========="
        % current_time
    )


    # =================================================
    # UDP
    # =================================================

    print("\nUDP")

    print(
        "Gói đã gửi       : %d"
        % udp["sent"]
    )

    print(
        "Gói nhận được    : %d"
        % udp["received"]
    )

    print(
        "Gói bị mất       : %d"
        % udp["lost"]
    )

    print(
        "Tỷ lệ mất gói    : %.2f%%"
        % udp["loss_percent"]
    )

    print(
        "Độ trễ           : %.2f ms"
        % udp["latency"]
    )

    print(
        "Dao động trễ     : %.2f ms"
        % udp["jitter"]
    )

    print(
        "Thông lượng      : %.3f Mbps"
        % udp["throughput"]
    )


    # =================================================
    # TCP
    # =================================================

    print("\nTCP")

    print(
        "Gói đã gửi       : %d"
        % tcp["sent"]
    )

    print(
        "Gói nhận được    : %d"
        % tcp["received"]
    )

    print(
        "Gói truyền lại   : %d"
        % tcp["retransmissions"]
    )

    print(
        "Độ trễ           : %.2f ms"
        % tcp["latency"]
    )

    print(
        "Dao động trễ     : %.2f ms"
        % tcp["jitter"]
    )

    print(
        "Thông lượng      : %.3f Mbps"
        % tcp["throughput"]
    )

    print(
        "============================================"
    )

    print(
        "Đã lưu dữ liệu vào: %s"
        % EXCEL_FILE
    )


    # =================================================
    # TRẢ VỀ CÁC ĐƯỜNG BIỂU ĐỒ
    # =================================================

    return (
        udp_latency_line,
        tcp_latency_line,

        udp_jitter_line,
        tcp_jitter_line,

        udp_throughput_line,
        tcp_throughput_line,

        udp_loss_line,
        tcp_retrans_line
    )


# =====================================================
# CHẠY BIỂU ĐỒ REALTIME
# =====================================================

ani = FuncAnimation(
    fig,
    update,
    interval=INTERVAL,
    cache_frame_data=False
)


# =====================================================
# CĂN CHỈNH GIAO DIỆN
# =====================================================

plt.tight_layout(
    rect=[0, 0, 1, 0.95]
)


# =====================================================
# HIỂN THỊ
# =====================================================

print("============================================")
print("BẮT ĐẦU MÔ PHỎNG TCP/UDP")
print("Dữ liệu Excel sẽ lưu tại:", EXCEL_FILE)
print("============================================")

plt.show()

# Lưu lần cuối khi đóng biểu đồ
workbook.save(EXCEL_FILE)

print("\nĐã kết thúc mô phỏng.")
print("File kết quả:", EXCEL_FILE)