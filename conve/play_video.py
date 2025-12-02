# play_video.py
import cv2
import sys


def play_mjpeg_file(filepath):
    """
    Mở và phát một file video bằng OpenCV.
    Nhấn phím 'q' để thoát.
    """
    print(f"--- Đang cố gắng mở và phát file: {filepath} ---")

    # Mở file video
    video_capture = cv2.VideoCapture(filepath)

    # Kiểm tra xem file có được mở thành công không
    if not video_capture.isOpened():
        print(f"\n[LỖI] Không thể mở file video: '{filepath}'")
        print("Vui lòng kiểm tra xem file có tồn tại và không bị lỗi hay không.")
        return

    print("\n[THÀNH CÔNG] File đã được mở.")
    print("Một cửa sổ video sẽ hiện ra.")
    print(">>> Nhấn phím 'q' trên cửa sổ video để thoát. <<<")

    while True:
        # Đọc từng frame của video
        # ret là True nếu đọc thành công, ngược lại là False (khi hết video)
        ret, frame = video_capture.read()

        # Nếu không đọc được frame (hết video), thoát khỏi vòng lặp
        if not ret:
            print("\nĐã phát đến cuối video hoặc có lỗi khi đọc frame.")
            break

        # Hiển thị frame trong một cửa sổ có tên 'Video Player'
        cv2.imshow('Video Player (Press Q to Quit)', frame)

        # Đợi 33 mili giây. Nếu người dùng nhấn 'q', thì thoát.
        # 1000ms / 30fps ≈ 33ms -> video sẽ chạy ở khoảng 30fps
        if cv2.waitKey(33) & 0xFF == ord('q'):
            break

    # Dọn dẹp sau khi kết thúc
    print("Đang giải phóng tài nguyên và đóng cửa sổ...")
    video_capture.release()
    cv2.destroyAllWindows()
    print("--- Hoàn tất ---")


if __name__ == "__main__":
    # Kiểm tra xem người dùng có cung cấp tên file không
    if len(sys.argv) != 2:
        print("\nSử dụng: python play_video.py <tên_file_video>")
        print("Ví dụ:  python play_video.py movie.mjpeg")
        sys.exit(1)

    video_file_path = sys.argv[1]
    play_mjpeg_file(video_file_path)