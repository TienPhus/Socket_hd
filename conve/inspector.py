import sys


def inspect_mjpeg(filepath):
    """
    Quét một file nhị phân và báo cáo số lượng marker JPEG (SOI và EOI) tìm thấy.
    """
    print("--- BẮT ĐẦU SCRIPT ĐIỀU TRA FILE ---")
    print(f"Đang phân tích file: {filepath}")
    print("-" * 40)

    try:
        with open(filepath, 'rb') as f:
            file_data = f.read()
        print(f"[OK] Đã đọc thành công {len(file_data)} bytes.")
    except FileNotFoundError:
        print(f"[LỖI] Không tìm thấy file: {filepath}")
        return

    # Marker bắt đầu (Start of Image) và kết thúc (End of Image) của JPEG
    SOI_MARKER = b'\xff\xd8'
    EOI_MARKER = b'\xff\xd9'

    # Đếm tất cả các lần xuất hiện
    soi_count = file_data.count(SOI_MARKER)
    eoi_count = file_data.count(EOI_MARKER)

    print("\n--- KẾT QUẢ PHÂN TÍCH ---")
    print(f"Số lượng marker BẮT ĐẦU (FF D8) tìm thấy: {soi_count}")
    print(f"Số lượng marker KẾT THÚC (FF D9) tìm thấy: {eoi_count}")
    print("-" * 40)

    # Phân tích sâu hơn: Tìm các cặp hoàn chỉnh
    complete_frames = 0
    current_pos = 0
    if soi_count > 0:
        print("Phân tích các cặp frame:")
        while current_pos < len(file_data):
            soi_pos = file_data.find(SOI_MARKER, current_pos)
            if soi_pos == -1:
                break

            eoi_pos = file_data.find(EOI_MARKER, soi_pos)
            if eoi_pos != -1:
                print(f"  - Tìm thấy frame hoàn chỉnh: Bắt đầu tại {soi_pos}, Kết thúc tại {eoi_pos}")
                complete_frames += 1
                current_pos = eoi_pos + 2
            else:
                print(f"  - Tìm thấy frame BẮT ĐẦU tại {soi_pos} nhưng KHÔNG có điểm kết thúc sau đó.")
                break  # Dừng lại khi gặp frame không hoàn chỉnh

    print("\n--- TỔNG KẾT ---")
    if soi_count == 0 and eoi_count == 0:
        print(">>> [KẾT LUẬN] File này hoàn toàn KHÔNG phải là một luồng JPEG thô.")
    elif soi_count > 0 and complete_frames == 0:
        print(">>> [KẾT LUẬN] File có chứa dữ liệu JPEG, nhưng các frame không hoàn chỉnh (thiếu marker kết thúc).")
    elif soi_count > 0 and complete_frames > 0:
        print(f">>> [KẾT LUẬN] File có chứa {complete_frames} frame JPEG hoàn chỉnh. Logic code converter đúng.")
    else:
        print(">>> [KẾT LUẬN] Cấu trúc file không xác định.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Sử dụng: python inspector.py <tên_file_cần_kiểm_tra>")
        sys.exit(1)

    file_to_inspect = sys.argv[1]
    inspect_mjpeg(file_to_inspect)