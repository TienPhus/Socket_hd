import sys


def convert_mjpeg_final(input_path, output_path):
    """
    Chuyển đổi một file MJPEG chuẩn thành định dạng có header 5-byte.
    Sử dụng logic quét đã được xác minh là đúng bởi inspector.py.
    """
    print("--- BẮT ĐẦU SCRIPT CHUYỂN ĐỔI (PHIÊN BẢN CUỐI CÙNG) ---")
    print(f"File đầu vào: {input_path}")
    print(f"File đầu ra:  {output_path}")

    try:
        with open(input_path, 'rb') as f_in:
            file_data = f_in.read()
    except FileNotFoundError:
        print(f"[LỖI] Không tìm thấy file '{input_path}'")
        return

    start_marker = b'\xff\xd8'
    end_marker = b'\xff\xd9'

    current_pos = 0
    frame_count = 0

    with open(output_path, 'wb') as f_out:
        while current_pos < len(file_data):
            # Tìm vị trí bắt đầu của frame tiếp theo
            soi_pos = file_data.find(start_marker, current_pos)
            if soi_pos == -1:
                break  # Không còn frame nào

            # Tìm vị trí kết thúc của frame đó, bắt đầu tìm từ vị trí soi_pos
            eoi_pos = file_data.find(end_marker, soi_pos)
            if eoi_pos == -1:
                # Điều này không nên xảy ra vì inspector đã xác nhận các frame là hoàn chỉnh
                print(f"Cảnh báo: Tìm thấy frame bắt đầu tại {soi_pos} nhưng không có điểm kết thúc.")
                break

            # Trích xuất dữ liệu frame
            frame_data = file_data[soi_pos: eoi_pos + 2]
            frame_len = len(frame_data)

            # Tạo header 5-byte
            header = str(frame_len).zfill(5).encode('utf-8')

            # Ghi header và dữ liệu frame
            f_out.write(header)
            f_out.write(frame_data)

            frame_count += 1

            # Cập nhật vị trí để tìm frame tiếp theo
            current_pos = eoi_pos + 2

    print("-" * 30)
    print("Chuyển đổi thành công!")
    print(f"Tổng số frame đã xử lý: {frame_count}")
    print(f"File đầu ra đã được lưu tại: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Sử dụng: python converter.py <file_dau_vao.mjpeg> <file_dau_ra.Mjpeg>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    convert_mjpeg_final(input_file, output_file)