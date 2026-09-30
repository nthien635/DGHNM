import random
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


# ============================================================
# CASE STUDY 2 - LONG FAT NETWORK (LFN)
# So sánh:
# 1. TCP Reno truyền thống
# 2. UDP/UDT-like
# 3. TCP BBR-like
#
# Đây là mô phỏng giáo dục đơn giản, không phải triển khai
# chính xác hoàn toàn Reno, UDT hoặc BBR thực tế.
# ============================================================


# ============================================================
# 1. CẤU HÌNH ĐƯỜNG TRUYỀN
# ============================================================

BANDWIDTH_MBPS = 1000          # 1 Gbps = 1000 Mbps
RTT_MS = 600                   # RTT = 600 ms
RTT_SECONDS = RTT_MS / 1000

FILE_SIZE_GB = 50              # File cần truyền = 50 GB

PACKET_LOSS = 0.02             # Xác suất nhiễu/mất gói = 2%

INTERVAL = 500                 # Cập nhật mỗi 500 ms = 0.5 giây
MAX_POINTS = 40                # Hiển thị 40 điểm gần nhất


# ============================================================
# 2. TÍNH BANDWIDTH-DELAY PRODUCT (BDP)
# ============================================================

# BDP = Bandwidth x RTT
#
# 1000 Mbps x 0.6 s = 600 Mbit
#
# 600 / 8 = 75 MB

BDP_MB = (
    BANDWIDTH_MBPS
    * RTT_SECONDS
) / 8


# ============================================================
# 3. THÔNG SỐ TCP RENO
# ============================================================

INITIAL_CWND_MB = 5.0

reno_cwnd_mb = INITIAL_CWND_MB


# ============================================================
# 4. THÔNG SỐ UDP/UDT-LIKE VÀ BBR-LIKE
# ============================================================

# UDP/UDT-like được mô phỏng ở mức sử dụng đường truyền cao.
# Khi có loss, có giảm nhẹ để biểu diễn chi phí phục hồi
# ở tầng ứng dụng.

UDT_NORMAL_UTILIZATION = 0.94
UDT_LOSS_UTILIZATION = 0.88

# BBR-like duy trì tốc độ dựa trên ước lượng bandwidth + RTT.
# Loss không làm giảm cwnd một nửa như Reno trong mô hình này.

BBR_NORMAL_UTILIZATION = 0.96
BBR_LOSS_UTILIZATION = 0.92


# ============================================================
# 5. FILE EXCEL
# ============================================================

EXCEL_FILE = "case_study2.xlsx"

workbook = Workbook()

worksheet = workbook.active
worksheet.title = "LFN Simulation"


headers = [
    "Thời gian (giây)",
    "Bandwidth tối đa (Mbps)",
    "RTT (ms)",
    "BDP (MB)",
    "Mất gói / nhiễu",

    "TCP Reno - cwnd (MB)",
    "TCP Reno - Throughput (Mbps)",
    "TCP Reno - Hiệu suất (%)",

    "UDP/UDT - Throughput (Mbps)",
    "UDP/UDT - Hiệu suất (%)",

    "TCP BBR - Throughput (Mbps)",
    "TCP BBR - Hiệu suất (%)"
]


worksheet.append(headers)


# In đậm tiêu đề
for cell in worksheet[1]:

    cell.font = Font(bold=True)

    cell.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )


# Điều chỉnh độ rộng cột
column_widths = {

    "A": 18,
    "B": 25,
    "C": 15,
    "D": 15,
    "E": 20,

    "F": 22,
    "G": 30,
    "H": 25,

    "I": 30,
    "J": 25,

    "K": 30,
    "L": 25
}


for column, width in column_widths.items():

    worksheet.column_dimensions[column].width = width


workbook.save(EXCEL_FILE)


# ============================================================
# 6. DỮ LIỆU BIỂU ĐỒ
# ============================================================

times = deque(maxlen=MAX_POINTS)


# Throughput
reno_throughput_data = deque(maxlen=MAX_POINTS)

udt_throughput_data = deque(maxlen=MAX_POINTS)

bbr_throughput_data = deque(maxlen=MAX_POINTS)


# Hiệu suất
reno_efficiency_data = deque(maxlen=MAX_POINTS)

udt_efficiency_data = deque(maxlen=MAX_POINTS)

bbr_efficiency_data = deque(maxlen=MAX_POINTS)


# TCP Reno cwnd
reno_cwnd_data = deque(maxlen=MAX_POINTS)


# Sự kiện mất gói
loss_event_data = deque(maxlen=MAX_POINTS)


current_time = 0


# ============================================================
# 7. MÔ PHỎNG TCP RENO
# ============================================================

def simulate_tcp_reno(packet_lost):

    global reno_cwnd_mb


    # Nếu xảy ra mất gói do nhiễu
    if packet_lost:

        # Reno coi loss như tín hiệu congestion
        # Mô phỏng giảm cửa sổ xuống một nửa

        reno_cwnd_mb = reno_cwnd_mb / 2


        # Không cho cwnd quá nhỏ
        if reno_cwnd_mb < 0.5:

            reno_cwnd_mb = 0.5


        action = "GIẢM cwnd do phát hiện mất gói"


    else:

        # Nếu không mất gói:
        # Reno tăng cửa sổ dần

        reno_cwnd_mb += 1.0


        # Không cần vượt quá BDP trong mô hình này

        if reno_cwnd_mb > BDP_MB:

            reno_cwnd_mb = BDP_MB


        action = "Tăng cwnd dần"


    # Throughput gần đúng:
    #
    # throughput = window / RTT
    #
    # cwnd đang tính bằng MB
    # x8 để đổi thành Mbit

    throughput = (
        reno_cwnd_mb
        * 8
    ) / RTT_SECONDS


    # Không được vượt quá bandwidth vật lý

    throughput = min(
        throughput,
        BANDWIDTH_MBPS
    )


    efficiency = (
        throughput
        / BANDWIDTH_MBPS
    ) * 100


    return {

        "cwnd": reno_cwnd_mb,

        "throughput": throughput,

        "efficiency": efficiency,

        "action": action
    }


# ============================================================
# 8. MÔ PHỎNG UDP / UDT-LIKE
# ============================================================

def simulate_udt(packet_lost):

    # UDT-like không sử dụng cơ chế giảm cwnd
    # giống TCP Reno trong mô hình đơn giản này.
    #
    # Reliability / retransmission được giả định xử lý
    # ở tầng ứng dụng.


    if packet_lost:

        utilization = UDT_LOSS_UTILIZATION

        action = (
            "Có loss - phục hồi ở tầng ứng dụng"
        )

    else:

        utilization = UDT_NORMAL_UTILIZATION

        action = (
            "Duy trì tốc độ truyền cao"
        )


    # Thêm một chút biến động cho mô phỏng realtime

    variation = random.uniform(
        -0.02,
        0.02
    )


    utilization += variation


    # Giới hạn utilization

    utilization = max(
        0,
        min(utilization, 1)
    )


    throughput = (
        BANDWIDTH_MBPS
        * utilization
    )


    efficiency = (
        throughput
        / BANDWIDTH_MBPS
    ) * 100


    return {

        "throughput": throughput,

        "efficiency": efficiency,

        "action": action
    }


# ============================================================
# 9. MÔ PHỎNG TCP BBR-LIKE
# ============================================================

def simulate_bbr(packet_lost):

    # Mô hình đơn giản:
    #
    # BBR-like dựa vào bandwidth + RTT.
    #
    # Khi có loss, không giảm cửa sổ xuống một nửa
    # như Reno trong mô phỏng này.


    if packet_lost:

        utilization = BBR_LOSS_UTILIZATION

        action = (
            "Có loss - vẫn duy trì theo bandwidth/RTT"
        )

    else:

        utilization = BBR_NORMAL_UTILIZATION

        action = (
            "Duy trì theo bandwidth/RTT"
        )


    variation = random.uniform(
        -0.015,
        0.015
    )


    utilization += variation


    utilization = max(
        0,
        min(utilization, 1)
    )


    throughput = (
        BANDWIDTH_MBPS
        * utilization
    )


    efficiency = (
        throughput
        / BANDWIDTH_MBPS
    ) * 100


    return {

        "throughput": throughput,

        "efficiency": efficiency,

        "action": action
    }


# ============================================================
# 10. TẠO CỬA SỔ BIỂU ĐỒ
# ============================================================

fig, axes = plt.subplots(
    2,
    2,
    figsize=(13, 8)
)


fig.suptitle(
    "CASE STUDY 2 - LONG FAT NETWORK\n"
    "1 Gbps - RTT 600 ms - Loss 2%",
    fontsize=14
)


# ============================================================
# BIỂU ĐỒ 1
# THROUGHPUT
# ============================================================

ax_throughput = axes[0][0]


reno_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="TCP Reno"
)


udt_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="UDP/UDT-like"
)


bbr_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="TCP BBR-like"
)


# Đường bandwidth tối đa 1000 Mbps
ax_throughput.axhline(
    y=BANDWIDTH_MBPS,
    linestyle="--",
    label="Bandwidth tối đa 1000 Mbps"
)


ax_throughput.set_title(
    "So sánh thông lượng"
)

ax_throughput.set_xlabel(
    "Thời gian (giây)"
)

ax_throughput.set_ylabel(
    "Throughput (Mbps)"
)

ax_throughput.set_ylim(
    0,
    1100
)

ax_throughput.grid(True)

ax_throughput.legend()


# ============================================================
# BIỂU ĐỒ 2
# HIỆU SUẤT SỬ DỤNG ĐƯỜNG TRUYỀN
# ============================================================

ax_efficiency = axes[0][1]


reno_efficiency_line, = ax_efficiency.plot(
    [],
    [],
    label="TCP Reno"
)


udt_efficiency_line, = ax_efficiency.plot(
    [],
    [],
    label="UDP/UDT-like"
)


bbr_efficiency_line, = ax_efficiency.plot(
    [],
    [],
    label="TCP BBR-like"
)


ax_efficiency.axhline(
    y=100,
    linestyle="--",
    label="100% đường truyền"
)


ax_efficiency.set_title(
    "Hiệu suất sử dụng đường truyền 1 Gbps"
)

ax_efficiency.set_xlabel(
    "Thời gian (giây)"
)

ax_efficiency.set_ylabel(
    "Hiệu suất (%)"
)

ax_efficiency.set_ylim(
    0,
    110
)

ax_efficiency.grid(True)

ax_efficiency.legend()


# ============================================================
# BIỂU ĐỒ 3
# TCP RENO CWND VÀ BDP
# ============================================================

ax_cwnd = axes[1][0]


reno_cwnd_line, = ax_cwnd.plot(
    [],
    [],
    label="TCP Reno cwnd"
)


# BDP = 75 MB
ax_cwnd.axhline(
    y=BDP_MB,
    linestyle="--",
    label="BDP = %.2f MB" % BDP_MB
)


ax_cwnd.set_title(
    "TCP Reno - Cửa sổ truyền và BDP"
)

ax_cwnd.set_xlabel(
    "Thời gian (giây)"
)

ax_cwnd.set_ylabel(
    "Cửa sổ truyền (MB)"
)

ax_cwnd.set_ylim(
    0,
    BDP_MB + 10
)

ax_cwnd.grid(True)

ax_cwnd.legend()


# ============================================================
# BIỂU ĐỒ 4
# SỰ KIỆN NHIỄU / MẤT GÓI
# ============================================================

ax_loss = axes[1][1]


loss_line, = ax_loss.plot(
    [],
    [],
    marker="o",
    label="Sự kiện mất gói"
)


ax_loss.set_title(
    "Nhiễu / mất gói 2%"
)

ax_loss.set_xlabel(
    "Thời gian (giây)"
)

ax_loss.set_ylabel(
    "Trạng thái"
)

ax_loss.set_ylim(
    -0.2,
    1.2
)

ax_loss.set_yticks(
    [0, 1]
)

ax_loss.set_yticklabels(
    ["Không", "Có"]
)

ax_loss.grid(True)

ax_loss.legend()


# ============================================================
# 11. HÀM UPDATE REALTIME
# ============================================================

def update(frame):

    global current_time


    # Mỗi lần update tăng 0.5 giây

    current_time += (
        INTERVAL / 1000
    )


    # ========================================================
    # TẠO SỰ KIỆN LOSS CHUNG
    # ========================================================

    packet_lost = (
        random.random()
        < PACKET_LOSS
    )


    # ========================================================
    # CHẠY 3 MÔ HÌNH
    # ========================================================

    reno = simulate_tcp_reno(
        packet_lost
    )


    udt = simulate_udt(
        packet_lost
    )


    bbr = simulate_bbr(
        packet_lost
    )


    # ========================================================
    # LƯU DỮ LIỆU BIỂU ĐỒ
    # ========================================================

    times.append(
        current_time
    )


    reno_throughput_data.append(
        reno["throughput"]
    )


    udt_throughput_data.append(
        udt["throughput"]
    )


    bbr_throughput_data.append(
        bbr["throughput"]
    )


    reno_efficiency_data.append(
        reno["efficiency"]
    )


    udt_efficiency_data.append(
        udt["efficiency"]
    )


    bbr_efficiency_data.append(
        bbr["efficiency"]
    )


    reno_cwnd_data.append(
        reno["cwnd"]
    )


    if packet_lost:

        loss_event_data.append(1)

    else:

        loss_event_data.append(0)


    # ========================================================
    # GHI EXCEL
    # ========================================================

    if packet_lost:

        loss_text = "Có"

    else:

        loss_text = "Không"


    worksheet.append([

        round(current_time, 1),

        BANDWIDTH_MBPS,

        RTT_MS,

        round(BDP_MB, 2),

        loss_text,

        round(
            reno["cwnd"],
            2
        ),

        round(
            reno["throughput"],
            2
        ),

        round(
            reno["efficiency"],
            2
        ),

        round(
            udt["throughput"],
            2
        ),

        round(
            udt["efficiency"],
            2
        ),

        round(
            bbr["throughput"],
            2
        ),

        round(
            bbr["efficiency"],
            2
        )
    ])


    # Lưu Excel realtime
    workbook.save(
        EXCEL_FILE
    )


    # ========================================================
    # CẬP NHẬT BIỂU ĐỒ THROUGHPUT
    # ========================================================

    reno_throughput_line.set_data(
        list(times),
        list(reno_throughput_data)
    )


    udt_throughput_line.set_data(
        list(times),
        list(udt_throughput_data)
    )


    bbr_throughput_line.set_data(
        list(times),
        list(bbr_throughput_data)
    )


    # ========================================================
    # CẬP NHẬT BIỂU ĐỒ HIỆU SUẤT
    # ========================================================

    reno_efficiency_line.set_data(
        list(times),
        list(reno_efficiency_data)
    )


    udt_efficiency_line.set_data(
        list(times),
        list(udt_efficiency_data)
    )


    bbr_efficiency_line.set_data(
        list(times),
        list(bbr_efficiency_data)
    )


    # ========================================================
    # CẬP NHẬT CWND
    # ========================================================

    reno_cwnd_line.set_data(
        list(times),
        list(reno_cwnd_data)
    )


    # ========================================================
    # CẬP NHẬT LOSS
    # ========================================================

    loss_line.set_data(
        list(times),
        list(loss_event_data)
    )


    # ========================================================
    # TRỤC THỜI GIAN
    # ========================================================

    if current_time > 20:

        xmin = current_time - 20
        xmax = current_time

    else:

        xmin = 0
        xmax = 20


    ax_throughput.set_xlim(
        xmin,
        xmax
    )


    ax_efficiency.set_xlim(
        xmin,
        xmax
    )


    ax_cwnd.set_xlim(
        xmin,
        xmax
    )


    ax_loss.set_xlim(
        xmin,
        xmax
    )


    # ========================================================
    # TERMINAL
    # ========================================================

    print(
        "\n=============================================="
    )

    print(
        "THỜI GIAN: %.1f giây"
        % current_time
    )

    print(
        "=============================================="
    )


    print("\nTHÔNG SỐ ĐƯỜNG TRUYỀN")

    print(
        "Dung lượng file       : %d GB"
        % FILE_SIZE_GB
    )

    print(
        "Bandwidth tối đa      : %d Mbps (1 Gbps)"
        % BANDWIDTH_MBPS
    )

    print(
        "RTT                   : %d ms"
        % RTT_MS
    )

    print(
        "BDP                   : %.2f MB"
        % BDP_MB
    )


    if packet_lost:

        print(
            "Nhiễu / mất gói      : CÓ"
        )

    else:

        print(
            "Nhiễu / mất gói      : KHÔNG"
        )


    # --------------------------------------------------------
    # TCP RENO
    # --------------------------------------------------------

    print("\nTCP RENO")

    print(
        "cwnd                  : %.2f MB"
        % reno["cwnd"]
    )

    print(
        "Thông lượng           : %.2f Mbps"
        % reno["throughput"]
    )

    print(
        "Hiệu suất             : %.2f%%"
        % reno["efficiency"]
    )

    print(
        "Phản ứng              : %s"
        % reno["action"]
    )


    # --------------------------------------------------------
    # UDP / UDT
    # --------------------------------------------------------

    print("\nUDP / UDT-LIKE")

    print(
        "Thông lượng           : %.2f Mbps"
        % udt["throughput"]
    )

    print(
        "Hiệu suất             : %.2f%%"
        % udt["efficiency"]
    )

    print(
        "Phản ứng              : %s"
        % udt["action"]
    )


    # --------------------------------------------------------
    # TCP BBR
    # --------------------------------------------------------

    print("\nTCP BBR-LIKE")

    print(
        "Thông lượng           : %.2f Mbps"
        % bbr["throughput"]
    )

    print(
        "Hiệu suất             : %.2f%%"
        % bbr["efficiency"]
    )

    print(
        "Phản ứng              : %s"
        % bbr["action"]
    )


    print(
        "\nĐã lưu Excel          : %s"
        % EXCEL_FILE
    )

    print(
        "=============================================="
    )


    return (

        reno_throughput_line,

        udt_throughput_line,

        bbr_throughput_line,

        reno_efficiency_line,

        udt_efficiency_line,

        bbr_efficiency_line,

        reno_cwnd_line,

        loss_line
    )


# ============================================================
# 12. THÔNG TIN BAN ĐẦU
# ============================================================

print(
    "===================================================="
)

print(
    "CASE STUDY 2 - LONG FAT NETWORK"
)

print(
    "===================================================="
)

print(
    "Dung lượng dữ liệu : %d GB"
    % FILE_SIZE_GB
)

print(
    "Bandwidth           : %d Mbps (1 Gbps)"
    % BANDWIDTH_MBPS
)

print(
    "RTT                 : %d ms"
    % RTT_MS
)

print(
    "Packet Loss         : %.2f%%"
    % (PACKET_LOSS * 100)
)

print(
    "BDP                 : %.2f MB"
    % BDP_MB
)

print(
    "----------------------------------------------------"
)

print(
    "Đang so sánh:"
)

print(
    "1. TCP Reno truyền thống"
)

print(
    "2. UDP/UDT-like"
)

print(
    "3. TCP BBR-like"
)

print(
    "----------------------------------------------------"
)

print(
    "File Excel          : %s"
    % EXCEL_FILE
)

print(
    "===================================================="
)


# ============================================================
# 13. CHẠY ANIMATION
# ============================================================

ani = FuncAnimation(

    fig,

    update,

    interval=INTERVAL,

    cache_frame_data=False
)


plt.tight_layout(
    rect=[0, 0, 1, 0.92]
)


plt.show()


# ============================================================
# 14. KẾT THÚC
# ============================================================

workbook.save(
    EXCEL_FILE
)


print(
    "\n===================================================="
)

print(
    "ĐÃ KẾT THÚC MÔ PHỎNG"
)

print(
    "File Excel: %s"
    % EXCEL_FILE
)

print(
    "===================================================="
)