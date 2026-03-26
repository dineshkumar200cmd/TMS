import cv2
import os

def flip_video(in_path, out_path):
    print(f"Processing {in_path} -> {out_path}")
    cap = cv2.VideoCapture(in_path)
    if not cap.isOpened():
        print(f"Failed to open {in_path}")
        return
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or fps != fps: fps = 30
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    count = 0
    while count < 300: # Take 10 seconds of video to be fast
        ret, frame = cap.read()
        if not ret: break
        out.write(cv2.flip(frame, 1))
        count += 1
    cap.release()
    out.release()
    print("Done")

flip_video('traffic_video.mp4', 'videos/north_road.mp4')
flip_video('traffic_video2.mp4', 'videos/south_road.mp4')
