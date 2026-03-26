import cv2
import os

def capture_preview(video_path, output_image):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open {video_path}")
        return
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(output_image, frame)
        print(f"Captured {output_image}")
    cap.release()

videos_to_check = [
    ('traffic_video.mp4', 'preview_traffic_video.png'),
    ('traffic_video2.mp4', 'preview_traffic_video2.png'),
    ('traffic_video3.mp4', 'preview_traffic_video3.png'),
    ('videos/north_road.mp4', 'preview_north.png')
]

for v, out in videos_to_check:
    if os.path.exists(v):
        capture_preview(v, out)
    else:
        print(f"Skipping {v}, does not exist")
