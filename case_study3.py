import random
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


# ============================================================
# CASE STUDY 3
# HTTP/2 + TCP vs HTTP/3 + QUIC/UDP
#
# Mục tiêu:
# - Minh họa ảnh hưởng của Packet Loss
# - Minh họa Head-of-Line Blocking
# - So sánh Page Load Time
# - So sánh Throughput
# - So sánh Connection Setup
#
# LƯU Ý:
# Đây là mô phỏng giáo dục đơn giản.
# Các giá trị không phải benchmark thực tế của HTTP/2/HTTP/3.
# ============================================================


# ============================================================
# 1. CẤU HÌNH MÔ PHỎNG
# ============================================================

RTT_MS = 100

PACKET_LOSS = 0.02

NUM_STREAMS = 6

INTERVAL = 500

MAX_POINTS = 40

BANDWIDTH_MBPS = 10


# HTTP/2 + TCP
HTTP2_SETUP_MS = 200

HTTP2_BASE_LOAD_MS = 700

HTTP2_LOSS_PENALTY_MS = 300


# HTTP/3 + QUIC
HTTP3_SETUP_MS = 100

HTTP3_BASE_LOAD_MS = 550

HTTP3_LOSS_PENALTY_MS = 100


# ============================================================
# 2. FILE EXCEL
# ============================================================

EXCEL_FILE = "case_study3.xlsx"

workbook = Workbook()

worksheet = workbook.active

worksheet.title = "HTTP3 QUIC Simulation"


headers = [

    "Thời gian (giây)",

    "RTT (ms)",

    "Packet Loss",

    "HTTP2 - Connection Setup (ms)",

    "HTTP2 - HOL Blocking",

    "HTTP2 - Page Load Time (ms)",

    "HTTP2 - Throughput (Mbps)",

    "HTTP3 - Connection Setup (ms)",

    "HTTP3 - Stream bị ảnh hưởng",

    "HTTP3 - HOL toàn connection",

    "HTTP3 - Page Load Time (ms)",

    "HTTP3 - Throughput (Mbps)"
]


worksheet.append(headers)


for cell in worksheet[1]:

    cell.font = Font(bold=True)

    cell.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )


column_widths = {

    "A": 18,

    "B": 15,

    "C": 18,

    "D": 30,

    "E": 25,

    "F": 30,

    "G": 28,

    "H": 30,

    "I": 25,

    "J": 28,

    "K": 30,

    "L": 28
}


for column, width in column_widths.items():

    worksheet.column_dimensions[column].width = width


workbook.save(EXCEL_FILE)


# ============================================================
# 3. DỮ LIỆU CHO BIỂU ĐỒ
# ============================================================

times = deque(maxlen=MAX_POINTS)


# Page Load Time

http2_load_data = deque(
    maxlen=MAX_POINTS
)

http3_load_data = deque(
    maxlen=MAX_POINTS
)


# Throughput

http2_throughput_data = deque(
    maxlen=MAX_POINTS
)

http3_throughput_data = deque(
    maxlen=MAX_POINTS
)


# HOL Blocking

http2_hol_data = deque(
    maxlen=MAX_POINTS
)

http3_hol_data = deque(
    maxlen=MAX_POINTS
)


# Packet Loss

loss_data = deque(
    maxlen=MAX_POINTS
)


current_time = 0


# ============================================================
# 4. MÔ PHỎNG HTTP/2 + TCP
# ============================================================

def simulate_http2(packet_lost):

    # HTTP/2 sử dụng TCP.
    #
    # Trong mô hình này:
    # Nếu TCP mất dữ liệu, dữ liệu phía sau trên cùng
    # TCP connection phải chờ phục hồi.
    #
    # Đây là transport-level Head-of-Line Blocking.


    if packet_lost:

        hol_blocking = 1

        page_load_time = (
            HTTP2_BASE_LOAD_MS
            + HTTP2_LOSS_PENALTY_MS
            + random.uniform(-30, 30)
        )

        action = (
            "TCP loss -> HOL Blocking -> phải chờ retransmission"
        )

    else:

        hol_blocking = 0

        page_load_time = (
            HTTP2_BASE_LOAD_MS
            + random.uniform(-30, 30)
        )

        action = (
            "Không loss -> truyền bình thường"
        )


    # Mô phỏng throughput.
    #
    # Khi HOL xảy ra, throughput hiệu dụng giảm.

    if packet_lost:

        throughput = random.uniform(
            5.5,
            7.0
        )

    else:

        throughput = random.uniform(
            8.0,
            9.2
        )


    return {

        "setup": HTTP2_SETUP_MS,

        "hol": hol_blocking,

        "load": page_load_time,

        "throughput": throughput,

        "action": action
    }


# ============================================================
# 5. MÔ PHỎNG HTTP/3 + QUIC
# ============================================================

def simulate_http3(packet_lost):

    # HTTP/3 sử dụng QUIC.
    #
    # QUIC chạy trên UDP nhưng tự cung cấp:
    #
    # - Reliability
    # - Retransmission
    # - Congestion Control
    # - Encryption
    # - Multiplexing
    #
    # Khi một QUIC stream bị mất dữ liệu,
    # các stream độc lập khác vẫn có thể tiếp tục.


    if packet_lost:

        affected_streams = 1

        hol_connection = 0

        page_load_time = (
            HTTP3_BASE_LOAD_MS
            + HTTP3_LOSS_PENALTY_MS
            + random.uniform(-20, 20)
        )

        action = (
            "1 stream bị ảnh hưởng, các stream khác vẫn tiếp tục"
        )

    else:

        affected_streams = 0

        hol_connection = 0

        page_load_time = (
            HTTP3_BASE_LOAD_MS
            + random.uniform(-20, 20)
        )

        action = (
            "Các QUIC stream truyền độc lập"
        )


    # Throughput HTTP/3 trong mô hình
    #
    # Khi loss xảy ra vẫn có giảm,
    # nhưng giảm ít hơn HTTP/2 vì không có
    # transport HOL giữa các stream độc lập.

    if packet_lost:

        throughput = random.uniform(
            8.0,
            9.0
        )

    else:

        throughput = random.uniform(
            9.0,
            9.8
        )


    return {

        "setup": HTTP3_SETUP_MS,

        "affected_streams": affected_streams,

        "hol": hol_connection,

        "load": page_load_time,

        "throughput": throughput,

        "action": action
    }


# ============================================================
# 6. TẠO 4 BIỂU ĐỒ
# ============================================================

fig, axes = plt.subplots(
    2,
    2,
    figsize=(13, 8)
)


fig.suptitle(
    "CASE STUDY 3 - HTTP/2 + TCP vs HTTP/3 + QUIC/UDP\n"
    "RTT 100 ms - Packet Loss 2%",
    fontsize=14
)


# ============================================================
# BIỂU ĐỒ 1
# PAGE LOAD TIME
# ============================================================

ax_load = axes[0][0]


http2_load_line, = ax_load.plot(
    [],
    [],
    label="HTTP/2 + TCP"
)


http3_load_line, = ax_load.plot(
    [],
    [],
    label="HTTP/3 + QUIC"
)


ax_load.set_title(
    "Page Load Time"
)

ax_load.set_xlabel(
    "Thời gian mô phỏng (giây)"
)

ax_load.set_ylabel(
    "Page Load Time (ms)"
)

ax_load.set_ylim(
    400,
    1100
)

ax_load.grid(True)

ax_load.legend()


# ============================================================
# BIỂU ĐỒ 2
# THROUGHPUT
# ============================================================

ax_throughput = axes[0][1]


http2_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="HTTP/2 + TCP"
)


http3_throughput_line, = ax_throughput.plot(
    [],
    [],
    label="HTTP/3 + QUIC"
)


ax_throughput.axhline(
    y=BANDWIDTH_MBPS,
    linestyle="--",
    label="Bandwidth tối đa 10 Mbps"
)


ax_throughput.set_title(
    "Throughput"
)

ax_throughput.set_xlabel(
    "Thời gian mô phỏng (giây)"
)

ax_throughput.set_ylabel(
    "Throughput (Mbps)"
)

ax_throughput.set_ylim(
    0,
    11
)

ax_throughput.grid(True)

ax_throughput.legend()


# ============================================================
# BIỂU ĐỒ 3
# HEAD-OF-LINE BLOCKING
# ============================================================

ax_hol = axes[1][0]


http2_hol_line, = ax_hol.plot(
    [],
    [],
    marker="o",
    label="HTTP/2 + TCP"
)


http3_hol_line, = ax_hol.plot(
    [],
    [],
    marker="o",
    label="HTTP/3 + QUIC"
)


ax_hol.set_title(
    "Transport Head-of-Line Blocking"
)

ax_hol.set_xlabel(
    "Thời gian mô phỏng (giây)"
)

ax_hol.set_ylabel(
    "Trạng thái"
)

ax_hol.set_ylim(
    -0.2,
    1.2
)

ax_hol.set_yticks(
    [0, 1]
)

ax_hol.set_yticklabels(
    ["Không", "Có"]
)

ax_hol.grid(True)

ax_hol.legend()


# ============================================================
# BIỂU ĐỒ 4
# PACKET LOSS
# ============================================================

ax_loss = axes[1][1]


loss_line, = ax_loss.plot(
    [],
    [],
    marker="o",
    label="Packet Loss"
)


ax_loss.set_title(
    "Sự kiện Packet Loss 2%"
)

ax_loss.set_xlabel(
    "Thời gian mô phỏng (giây)"
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
# 7. HÀM UPDATE REALTIME
# ============================================================

def update(frame):

    global current_time


    # Mỗi lần cập nhật tăng 0.5 giây

    current_time += (
        INTERVAL / 1000
    )


    # ========================================================
    # TẠO PACKET LOSS
    # ========================================================

    packet_lost = (
        random.random()
        < PACKET_LOSS
    )


    # ========================================================
    # CHẠY HTTP/2 VÀ HTTP/3
    # ========================================================

    http2 = simulate_http2(
        packet_lost
    )


    http3 = simulate_http3(
        packet_lost
    )


    # ========================================================
    # LƯU DỮ LIỆU BIỂU ĐỒ
    # ========================================================

    times.append(
        current_time
    )


    http2_load_data.append(
        http2["load"]
    )


    http3_load_data.append(
        http3["load"]
    )


    http2_throughput_data.append(
        http2["throughput"]
    )


    http3_throughput_data.append(
        http3["throughput"]
    )


    http2_hol_data.append(
        http2["hol"]
    )


    http3_hol_data.append(
        http3["hol"]
    )


    if packet_lost:

        loss_data.append(1)

    else:

        loss_data.append(0)


    # ========================================================
    # GHI EXCEL
    # ========================================================

    if packet_lost:

        loss_text = "Có"

    else:

        loss_text = "Không"


    if http2["hol"] == 1:

        http2_hol_text = "Có"

    else:

        http2_hol_text = "Không"


    if http3["hol"] == 1:

        http3_hol_text = "Có"

    else:

        http3_hol_text = "Không"


    worksheet.append([

        round(
            current_time,
            1
        ),

        RTT_MS,

        loss_text,

        http2["setup"],

        http2_hol_text,

        round(
            http2["load"],
            2
        ),

        round(
            http2["throughput"],
            2
        ),

        http3["setup"],

        http3["affected_streams"],

        http3_hol_text,

        round(
            http3["load"],
            2
        ),

        round(
            http3["throughput"],
            2
        )
    ])


    # Lưu Excel realtime

    workbook.save(
        EXCEL_FILE
    )


    # ========================================================
    # CẬP NHẬT PAGE LOAD TIME
    # ========================================================

    http2_load_line.set_data(
        list(times),
        list(http2_load_data)
    )


    http3_load_line.set_data(
        list(times),
        list(http3_load_data)
    )


    # ========================================================
    # CẬP NHẬT THROUGHPUT
    # ========================================================

    http2_throughput_line.set_data(
        list(times),
        list(http2_throughput_data)
    )


    http3_throughput_line.set_data(
        list(times),
        list(http3_throughput_data)
    )


    # ========================================================
    # CẬP NHẬT HOL BLOCKING
    # ========================================================

    http2_hol_line.set_data(
        list(times),
        list(http2_hol_data)
    )


    http3_hol_line.set_data(
        list(times),
        list(http3_hol_data)
    )


    # ========================================================
    # CẬP NHẬT PACKET LOSS
    # ========================================================

    loss_line.set_data(
        list(times),
        list(loss_data)
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


    ax_load.set_xlim(
        xmin,
        xmax
    )


    ax_throughput.set_xlim(
        xmin,
        xmax
    )


    ax_hol.set_xlim(
        xmin,
        xmax
    )


    ax_loss.set_xlim(
        xmin,
        xmax
    )


    # ========================================================
    # HIỂN THỊ TERMINAL
    # ========================================================

    print(
        "\n===================================================="
    )

    print(
        "THỜI GIAN: %.1f giây"
        % current_time
    )

    print(
        "===================================================="
    )


    # --------------------------------------------------------
    # THÔNG SỐ MẠNG
    # --------------------------------------------------------

    print(
        "\nTHÔNG SỐ MẠNG"
    )


    print(
        "RTT                    : %d ms"
        % RTT_MS
    )


    print(
        "Bandwidth              : %d Mbps"
        % BANDWIDTH_MBPS
    )


    print(
        "Số Web Stream          : %d"
        % NUM_STREAMS
    )


    print(
        "Xác suất Packet Loss   : %.2f%%"
        % (PACKET_LOSS * 100)
    )


    if packet_lost:

        print(
            "Packet Loss            : CÓ"
        )

    else:

        print(
            "Packet Loss            : KHÔNG"
        )


    # --------------------------------------------------------
    # HTTP/2 + TCP
    # --------------------------------------------------------

    print(
        "\nHTTP/2 + TCP"
    )


    print(
        "Connection Setup       : %d ms"
        % http2["setup"]
    )


    if http2["hol"] == 1:

        print(
            "HOL Blocking           : CÓ"
        )

    else:

        print(
            "HOL Blocking           : KHÔNG"
        )


    print(
        "Page Load Time         : %.2f ms"
        % http2["load"]
    )


    print(
        "Throughput             : %.2f Mbps"
        % http2["throughput"]
    )


    print(
        "Phản ứng               : %s"
        % http2["action"]
    )


    # --------------------------------------------------------
    # HTTP/3 + QUIC
    # --------------------------------------------------------

    print(
        "\nHTTP/3 + QUIC/UDP"
    )


    print(
        "Connection Setup       : %d ms"
        % http3["setup"]
    )


    print(
        "Stream bị ảnh hưởng    : %d/%d"
        % (
            http3["affected_streams"],
            NUM_STREAMS
        )
    )


    if http3["hol"] == 1:

        print(
            "HOL toàn connection    : CÓ"
        )

    else:

        print(
            "HOL toàn connection    : KHÔNG"
        )


    print(
        "Page Load Time         : %.2f ms"
        % http3["load"]
    )


    print(
        "Throughput             : %.2f Mbps"
        % http3["throughput"]
    )


    print(
        "Phản ứng               : %s"
        % http3["action"]
    )


    print(
        "\nĐã lưu Excel           : %s"
        % EXCEL_FILE
    )


    print(
        "===================================================="
    )


    return (

        http2_load_line,

        http3_load_line,

        http2_throughput_line,

        http3_throughput_line,

        http2_hol_line,

        http3_hol_line,

        loss_line
    )


# ============================================================
# 8. HIỂN THỊ THÔNG TIN BAN ĐẦU
# ============================================================

print(
    "===================================================="
)

print(
    "CASE STUDY 3"
)

print(
    "HTTP/2 + TCP vs HTTP/3 + QUIC/UDP"
)

print(
    "===================================================="
)


print(
    "RTT                  : %d ms"
    % RTT_MS
)


print(
    "Bandwidth            : %d Mbps"
    % BANDWIDTH_MBPS
)


print(
    "Packet Loss          : %.2f%%"
    % (PACKET_LOSS * 100)
)


print(
    "Số Web Stream        : %d"
    % NUM_STREAMS
)


print(
    "Chu kỳ cập nhật      : %.1f giây"
    % (INTERVAL / 1000)
)


print(
    "----------------------------------------------------"
)


print(
    "Đang so sánh:"
)


print(
    "1. HTTP/2 chạy trên TCP"
)


print(
    "2. HTTP/3 chạy trên QUIC/UDP"
)


print(
    "----------------------------------------------------"
)


print(
    "Metrics:"
)


print(
    "- Connection Setup"
)


print(
    "- Page Load Time"
)


print(
    "- Throughput"
)


print(
    "- Head-of-Line Blocking"
)


print(
    "- Packet Loss"
)


print(
    "----------------------------------------------------"
)


print(
    "File Excel           : %s"
    % EXCEL_FILE
)


print(
    "===================================================="
)


# ============================================================
# 9. CHẠY ANIMATION
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
# 10. KẾT THÚC
# ============================================================

workbook.save(
    EXCEL_FILE
)


print(
    "\n===================================================="
)


print(
    "ĐÃ KẾT THÚC MÔ PHỎNG CASE STUDY 3"
)


print(
    "File Excel: %s"
    % EXCEL_FILE
)


print(
    "===================================================="
)