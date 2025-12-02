from tkinter import *
from tkinter import messagebox as tkMessageBox
from io import BytesIO
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import time
from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3

    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        print(">>> ĐANG Ở TRONG Client.__init__")
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)

        #---------------------------------------------------------------------------#
            #Các biến cần thêm để xử lý video HD
        self.DISPLAY_WIDTH = 480
        self.DISPLAY_HEIGHT = 360
        #Để video HD display chính xác res củ thì cần ép res của video HD lại
        self.fileNameSD = filename  # Lưu tên file SD gốc
        # Tự động tạo tên file HD (giả định quy tắc đặt tên)
        self.fileNameHD = filename.replace('.mjpeg', '_hd.mjpeg').replace('.Mjpeg', '_hd.Mjpeg')
        self.currentQuality = 'SD'  # Bắt đầu với chất lượng SD
        self.fileName = self.fileNameSD  # fileName hiện tại là SD
        self.isSwitching = False
        self.reassembly_buffer = b''
        self.rtspRunning = threading.Event()
        self.autoPlayAfterSwitch = False #Khi video SD đang pause thì khi switch vẫn sẽ pause
        #---------------------------------------------------------------------------#

        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        print(">>> ĐÃ KẾT NỐI SERVER XONG, CHUẨN BỊ KẾT THÚC INIT")
        self.frameNbr = 0

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        # ---------------------------------------------------------------------------#
        #Switch quality button
        self.switch = Button(self.master, width=20, padx=3, pady=3)
        self.switch["text"] = "Switch to HD"
        self.switch["command"] = self.switchQuality
        self.switch.grid(row=3, column=1, padx=2, pady=2)  # Đặt ở vị trí hợp lý
        self.switch["state"] = "disabled"
        # ---------------------------------------------------------------------------#

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W + E + N + S, padx=5, pady=5)

    def setupMovie(self):
        """Setup button handler. Starts a new RTSP session."""
        if self.state == self.INIT:
            # Khởi động luồng lắng nghe cho phiên MỚI này
            self.rtspRunning.set()
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            print("Đã khởi động luồng recvRtspReply cho phiên mới.")
            self.sendRtspRequest(self.SETUP)

    #Exit client mạnh hơn
    def exitClient(self):
        """Handler for Teardown button and window close."""
        self.cleanup()  # Gọi hàm dọn dẹp
        self.master.destroy()  # Đóng cửa sổ

    # ---------------------------------------------------------------------------#
    # Tạo hàm dọn dẹp mới
    def cleanup(self):
        """Stops threads and closes sockets cleanly."""
        if self.state == self.INIT:
            return

        print("Bắt đầu dọn dẹp phiên...")

        # 1. Dừng các luồng client đang chạy
        if hasattr(self, 'playEvent'):
            self.playEvent.set()
        if hasattr(self, 'rtspRunning'):
            self.rtspRunning.clear()

        # 2. Gửi TEARDOWN để báo cho server (chỉ khi socket còn mở)
        #    Chúng ta không cần đợi phản hồi, chỉ cần "bắn và quên"
        try:
            # Tạo request teardown thủ công
            self.rtspSeq += 1
            request = f"TEARDOWN {self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}\n"
            self.rtspSocket.send(request.encode('utf-8'))
            print("Đã gửi TEARDOWN request.")
        except OSError:
            print("Không thể gửi TEARDOWN (socket có thể đã đóng).")

        # Đợi một chút để server xử lý
        time.sleep(0.2)

        # 3. Đóng các socket một cách mạnh mẽ
        try:
            self.rtspSocket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.rtspSocket.close()
            print("Đã đóng RTSP socket.")
        except OSError:
            pass

        try:
            self.rtpSocket.close()
            print("Đã đóng RTP socket.")
        except OSError:
            pass

        # 4. Cuối cùng, reset trạng thái
        self.state = self.INIT
        print("Đã dọn dẹp xong.")
    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
        else:
            print(">>> State is NOT PLAYING. Ignoring PAUSE request.")

    # ---------------------------------------------------------------------------#

    # ---------------------------------------------------------------------------#
    #Thiết lập PLAY cho SD và HD
    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            self.playEvent = threading.Event()
            self.playEvent.clear()

            if self.currentQuality == 'HD':
                print("Bắt đầu luồng nhận HD (có tái lắp ráp).")
                self.reassembly_buffer = b''  # Luôn reset buffer trước khi bắt đầu
                threading.Thread(target=self.listenRtpHD).start()
            else:
                print("Bắt đầu luồng nhận SD (logic gốc).")
                threading.Thread(target=self.listenRtp).start()

            self.sendRtspRequest(self.PLAY)

    # ---------------------------------------------------------------------------#
    def listenRtp(self):
        """Luồng nhận cho video SD."""
        while not self.playEvent.is_set():
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    currFrameNbr = rtpPacket.seqNum()
                    if currFrameNbr > self.frameNbr:
                        self.frameNbr = currFrameNbr
                        print(f"SD Seq Num: {currFrameNbr}")
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
            except Exception as e:
                # Đã thêm print nên có thể bỏ qua
                pass # Lỗi đã được in ra

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()

        return cachename

    # ---------------------------------------------------------------------------#
    #Sửa để tránh việc video hd tự bị resize
    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        try:
            # Mở ảnh từ file
            image = Image.open(imageFile)
            resized_image = image.resize((self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), Image.Resampling.LANCZOS)

            # Chuyển thành đối tượng có thể hiển thị
            photo = ImageTk.PhotoImage(resized_image)

            # Cấu hình label để hiển thị ảnh đã co
            self.label.configure(image=photo, width=self.DISPLAY_WIDTH, height=self.DISPLAY_HEIGHT)
            self.label.image = photo
        except Exception as e:
            print(f"Lỗi khi cập nhật frame SD: {e}")

    # ---------------------------------------------------------------------------#
    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        print(">>> ĐANG CỐ KẾT NỐI TỚI SERVER...")
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
            print(">>> KẾT NỐI THÀNH CÔNG!")
        except Exception as e:
            tkMessageBox.showwarning('Connection Failed', f'Connection to \'{self.serverAddr}\' failed: {e}')
            self.rtspSocket = None

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""
        request = ""  # Khởi tạo biến

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            self.rtspSeq = 1
            request = f"SETUP {self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Transport: TCP/UDP ; client_port = {self.rtpPort}\n"
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq += 1
            request = f"PLAY {self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}\n"
            self.requestSent = self.PLAY

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq += 1
            request = f"PAUSE {self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}\n"
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN:  # Luôn cho phép gửi TEARDOWN
            self.rtspSeq += 1
            request = f"TEARDOWN {self.fileName} RTSP/1.0\n"
            request += f"CSeq: {self.rtspSeq}\n"
            request += f"Session: {self.sessionId}\n"
            self.requestSent = self.TEARDOWN

        # Gửi request nếu nó được tạo ra
        if request:
            try:
                self.rtspSocket.send(request.encode('utf-8'))
                print('\nData sent:\n' + request)
            except OSError as e:
                print(f"Lỗi khi gửi request (socket có thể đã đóng): {e}")

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while self.rtspRunning.is_set():  # Chỉ chạy khi cờ được set
            try:
                reply = self.rtspSocket.recv(1024)
                if not reply:  # Server đã đóng kết nối
                    break
                self.parseRtspReply(reply.decode("utf-8"))
            except ConnectionAbortedError:
                print("Kết nối RTSP đã bị đóng bởi client.")
                break
            except OSError as e:
                # Bắt lỗi 10038 và thoát một cách nhẹ nhàng
                if e.winerror == 10038:
                    print("Socket RTSP đã được đóng, luồng recvRtspReply kết thúc.")
                    break
                else:
                    raise  # Ném lại các lỗi OSError khác

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                break


    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session

            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        self.state = self.READY
                        self.openRtpPort()

                        print("SETUP thành công. Client đang ở trạng thái READY.")
                    # ---------------------------------------------------------------------------#
                        # --- LOGIC KHÔI PHỤC TRẠNG THÁI MỚI ---
                        if self.isSwitching:
                            self.isSwitching = False  # Reset cờ switch

                            if self.autoPlayAfterSwitch:
                                # Nếu trước đó đang PLAYING, tự động PLAY lại
                                print("Khôi phục trạng thái: Tự động PLAY.")
                                self.playMovie()
                            else:
                                # Nếu trước đó đang PAUSED, chỉ cần cập nhật UI
                                print("Khôi phục trạng thái: Giữ nguyên PAUSED.")
                                self.start["state"] = "normal"
                                self.pause["state"] = "disabled"
                                self.switch["state"] = "disabled"

                        # Cập nhật UI cho lần SETUP đầu tiên (không phải switch)
                        else:
                            self.start["state"] = "normal"
                            self.pause["state"] = "disabled"
                            self.switch["state"] = "disabled"
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                        self.start["state"] = "disabled"
                        self.pause["state"] = "normal"
                        self.switch["state"] = "normal"
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        self.start["state"] = "normal"
                        self.pause["state"] = "disabled"
                        self.switch["state"] = "normal"
                        if hasattr(self, 'playEvent'):
                            self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        self.rtspRunning.clear()
                    # ---------------------------------------------------------------------------#

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)


        try:
            # Bind the socket to the address using the RTP port given by the client user
            self.rtpSocket.bind(('', self.rtpPort))
        except:
            tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    # ---------------------------------------------------------------------------#
    #Hàm để xử lý việc chuyển chất lượng
    def switchQuality(self):
        """Dừng phiên hiện tại, ... ghi nhớ trạng thái PLAYING/PAUSED."""
        if self.state != self.PLAYING and self.state != self.READY:
            print("Chỉ có thể chuyển chất lượng khi video đang phát hoặc tạm dừng.")
            return

        print("--- BẮT ĐẦU QUÁ TRÌNH CHUYỂN ĐỔI CHẤT LƯỢNG ---")

        # Ghi nhớ trạng thái hiện tại
        was_playing = (self.state == self.PLAYING)

        # Dọn dẹp hoàn toàn phiên cũ
        self.cleanup()
        time.sleep(0.1)

        # Thay đổi chất lượng và tên file
        if self.currentQuality == 'SD':
            self.currentQuality = 'HD'
            self.fileName = self.fileNameHD
            self.switch["text"] = "Switch to SD"
        else:
            self.currentQuality = 'SD'
            self.fileName = self.fileNameSD
            self.switch["text"] = "Switch to HD"

        # Reset các biến cho phiên mới
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.frameNbr = 0
        self.isSwitching = True
        self.autoPlayAfterSwitch = was_playing  # Đặt cờ tự động play

        # Bắt đầu lại từ đầu
        print("Bắt đầu lại phiên mới...")
        self.connectToServer()
        if self.rtspSocket:
            self.setupMovie()

    # ---------------------------------------------------------------------------#
    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie() # Tạm dừng để người dùng suy nghĩ
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else: # Khi người dùng nhấn cancel, resume playing.
             # Chú ý: playMovie bây giờ sẽ tạo lại luồng
            self.playMovie()

    # ---------------------------------------------------------------------------#
    #Các hàm để xử lý HD
    #Phải chạy từ RAM vì phần cứng xử lý không kịp
    def listenRtpHD(self):
        """Luồng nhận cho video HD, có tái lắp ráp frame."""
        while not self.playEvent.is_set():
            try:
                # Kích thước buffer nhận có thể cần lớn hơn
                data, addr = self.rtpSocket.recvfrom(40960)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    self.reassembly_buffer += rtpPacket.getPayload()

                    # Nếu đây là gói cuối cùng của một frame
                    if rtpPacket.marker() == 1:
                        self.frameNbr += 1
                        print(
                            f"Đã nhận hoàn chỉnh frame HD #{self.frameNbr}, kích thước: {len(self.reassembly_buffer)} bytes.")
                        self.updateMovieInMemory(self.reassembly_buffer)
                        # Reset buffer để chuẩn bị cho frame tiếp theo
                        self.reassembly_buffer = b''
            except socket.timeout:
                continue  # Hết giờ chờ, tiếp tục vòng lặp
            except Exception as e:
                print(f"Lỗi trong luồng HD: {e}")
                self.reassembly_buffer = b''  # Nếu lỗi, bỏ frame hiện tại và reset

    def updateMovieInMemory(self, frameData):
        """Hiển thị ảnh từ dữ liệu trong RAM."""
        try:
            # Mở ảnh từ luồng byte trong bộ nhớ
            image_stream = BytesIO(frameData)
            image = Image.open(image_stream)

            # --- PHẦN QUAN TRỌNG NHẤT ---
            # Co ảnh HD về kích thước hiển thị chuẩn với thuật toán chất lượng cao
            # Image.Resampling.LANCZOS là một trong những thuật toán tốt nhất
            resized_image = image.resize((self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), Image.Resampling.LANCZOS)

            # Chuyển thành đối tượng có thể hiển thị
            photo = ImageTk.PhotoImage(resized_image)

            # Cấu hình label để hiển thị ảnh đã co
            # Chúng ta cũng đặt width và height ở đây để đảm bảo Label không bị co lại
            self.label.configure(image=photo, width=self.DISPLAY_WIDTH, height=self.DISPLAY_HEIGHT)
            self.label.image = photo
        except Exception as e:
            print(f"Không thể hiển thị frame HD (có thể bị lỗi): {e}")
    # ---------------------------------------------------------------------------#
