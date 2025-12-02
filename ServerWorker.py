from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream, VideoStreamHD
from RtpPacket import RtpPacket


class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    SWITCH = 'SWITCH'

    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2

    clientInfo = {}

    def __init__(self, clientInfo):
        self.clientInfo = clientInfo

    def run(self):
        print(">>> ServerWorker.run() called. Starting new thread to listen for requests.")
        threading.Thread(target=self.recvRtspRequest).start()

    def recvRtspRequest(self):
        """Receive RTSP request from the client."""
        print(">>> Thread for recvRtspRequest has started. Waiting for data...")
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:
            data = connSocket.recv(256)
            if data:
                print("Data received:\n" + data.decode("utf-8"))
                self.processRtspRequest(data.decode("utf-8"))

    # ---------------------------------------------------------------------------#
    #Thêm quá trình xử lý HD
    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
        # Get the request type
        request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]

        # Get the media file name
        filename = line1[1]

        # Get the RTSP sequence number
        seq = request[1].split(' ')

        # Process SETUP request
        if requestType == self.SETUP:
            if self.state == self.INIT:
                print("processing SETUP\n")

                # --- LOGIC LỰA CHỌN ĐÃ SỬA LỖI ---
                is_hd = '_hd' in filename
                self.clientInfo['is_hd'] = is_hd

                try:
                    if is_hd:
                        print(">>> Yêu cầu video HD, sử dụng VideoStreamHD.")
                        self.clientInfo['videoStream'] = VideoStreamHD(filename)
                    else:
                        print(">>> Yêu cầu video SD, sử dụng VideoStream gốc.")
                        self.clientInfo['videoStream'] = VideoStream(filename)

                    self.state = self.READY
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                    return  # Thoát nếu không mở được file
                # --- KẾT THÚC SỬA LỖI ---

                # Generate a randomized RTSP session ID
                self.clientInfo['session'] = randint(100000, 999999)

                # Send RTSP reply
                self.replyRtsp(self.OK_200, seq[1])

                # Get the RTP/UDP port from the last line
                self.clientInfo['rtpPort'] = request[2].split('=')[1].strip()

        # Process PLAY request
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print("processing PLAY\n")
                self.state = self.PLAYING

                # Create a new socket for RTP/UDP
                self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                self.replyRtsp(self.OK_200, seq[1])

                # Create a new thread and start sending RTP packets
                self.clientInfo['event'] = threading.Event()
                if self.clientInfo.get('is_hd', False):  # Dùng get() để an toàn
                    print(">>> Lựa chọn luồng gửi HD (có phân mảnh).")
                    target_function = self.sendRtpHD  # Chọn hàm HD
                else:
                    print(">>> Lựa chọn luồng gửi SD (logic gốc).")
                    target_function = self.sendRtp  # Chọn hàm SD

                    # Khởi động luồng với hàm đã được chọn
                self.clientInfo['worker'] = threading.Thread(target=target_function)
                self.clientInfo['worker'].start()

        # Process PAUSE request
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY

                self.clientInfo['event'].set()

                self.replyRtsp(self.OK_200, seq[1])

        # Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")

            # 1. Ra hiệu cho luồng dừng lại
            self.clientInfo['event'].set()

            # 2. Gửi phản hồi OK cho client TRƯỚC KHI đợi
            self.replyRtsp(self.OK_200, seq[1])

            # 3. ĐỢI cho luồng worker thực sự kết thúc.
            #    Đây là bước quan trọng nhất bị thiếu.
            if 'worker' in self.clientInfo and self.clientInfo['worker'].is_alive():
                print("Waiting for worker thread to terminate...")
                self.clientInfo['worker'].join()
                print("Worker thread terminated.")

            # 4. Bây giờ mới đóng socket một cách an toàn
            if 'rtpSocket' in self.clientInfo:
                self.clientInfo['rtpSocket'].close()

    # ---------------------------------------------------------------------------#

    def sendRtp(self):
        """Send RTP packets over UDP."""
        while True:
            self.clientInfo['event'].wait(0.04)

            # Stop sending if request is PAUSE or TEARDOWN
            if self.clientInfo['event'].isSet():
                break

            data = self.clientInfo['videoStream'].nextFrame()
            if data:
                frameNumber = self.clientInfo['videoStream'].frameNbr()
                try:
                    address = self.clientInfo['rtspSocket'][1][0]
                    port = int(self.clientInfo['rtpPort'])
                    self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber), (address, port))
                except Exception as e:  # Sửa lại để bắt và in ra lỗi cụ thể
                    print(f"Connection Error while sending RTP packet: {e}")
                    # In thêm thông tin để debug
                    print(f"  - Target address: {address}")
                    print(f"  - Target port: {self.clientInfo.get('rtpPort', 'NOT FOUND')}")
                    break  # Thoát khỏi vòng lặp nếu có lỗi
        # print('-'*60)
        # traceback.print_exc(file=sys.stdout)
        # print('-'*60)

    def makeRtp(self, payload, frameNbr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26  # MJPEG type
        seqnum = frameNbr
        ssrc = 0

        rtpPacket = RtpPacket()

        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)

        return rtpPacket.getPacket()

    def replyRtsp(self, code, seq):
        """Send RTSP reply to the client."""
        if code == self.OK_200:
            # print("200 OK")
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
            connSocket = self.clientInfo['rtspSocket'][0]
            connSocket.send(reply.encode())

        # Error messages
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")

    # ---------------------------------------------------------------------------#
    #Các hàm để xử lý video HD
        #1. SendRtp nhưng dùng riêng cho video hd
    def sendRtpHD(self):
        """Send RTP packets over UDP, with fragmentation for large frames."""
        MAX_PAYLOAD_SIZE = 1400  # Kích thước an toàn
        packet_seq_num = self.clientInfo.get('rtp_seq_num', 0)  # Lấy seq num nếu có

        while True:
            # Dùng tốc độ cao hơn cho HD, ví dụ 30fps
            self.clientInfo['event'].wait(1 / 30)

            if self.clientInfo['event'].isSet():
                break

            data = self.clientInfo['videoStream'].nextFrame()
            if data:
                remaining_data = data
                while remaining_data:
                    payload = remaining_data[:MAX_PAYLOAD_SIZE]
                    remaining_data = remaining_data[MAX_PAYLOAD_SIZE:]

                    marker = 1 if not remaining_data else 0

                    try:
                        address = self.clientInfo['rtspSocket'][1][0]
                        port = int(self.clientInfo['rtpPort'])

                        # Sử dụng một hàm makeRtp có hỗ trợ marker
                        packet = self.makeRtpWithMarker(payload, packet_seq_num, marker)
                        self.clientInfo['rtpSocket'].sendto(packet, (address, port))

                        packet_seq_num += 1
                    except Exception as e:
                        print(f"Lỗi khi gửi gói tin HD: {e}")
                        break
            else:
                print("Hết video HD.")
                break
        self.clientInfo['rtp_seq_num'] = packet_seq_num  # Lưu lại seq num

    # Tạo một hàm makeRtp mới để không ảnh hưởng đến code gốc
    def makeRtpWithMarker(self, payload, seqnum, marker):
        """RTP-packetize with an explicit marker bit."""
        version = 2;
        padding = 0;
        extension = 0;
        cc = 0;
        pt = 26;
        ssrc = 0
        rtpPacket = RtpPacket()
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
        return rtpPacket.getPacket()
    # ---------------------------------------------------------------------------#
