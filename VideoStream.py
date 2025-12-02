class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data: 
			framelength = int(data)
							
			# Read the current frame
			data = self.file.read(framelength)
			self.frameNum += 1
		return data
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum

#---------------------------------------------------------------------------#
#Tạo class riêng để chạy video HD tránh xung đột với SD
class VideoStreamHD:
    def __init__(self, filename):
        self.filename = filename
        try:
            with open(filename, 'rb') as f:
                self.data = f.read()
        except IOError:
            raise
        self.current_pos = 0
        self.frameNum = 0

    def nextFrame(self):
        """Lấy frame tiếp theo bằng cách tìm JPEG markers."""
        if self.current_pos >= len(self.data):
            return None

        start_marker = b'\xff\xd8'
        end_marker = b'\xff\xd9'

        soi_pos = self.data.find(start_marker, self.current_pos)
        if soi_pos == -1: return None

        eoi_pos = self.data.find(end_marker, soi_pos)
        if eoi_pos == -1: return None

        frame_data = self.data[soi_pos: eoi_pos + 2]
        self.current_pos = eoi_pos + 2
        self.frameNum += 1
        return frame_data

    def frameNbr(self):
        return self.frameNum
