import { useEffect, useRef, useState } from "react";

const MAX_LONG_SIDE = 1280;
const JPEG_QUALITY = 0.8;

function cameraMessage(error) {
  if (!navigator.mediaDevices?.getUserMedia) {
    return "This browser cannot open a camera. Use a phone with HTTPS, or localhost.";
  }
  if (error.name === "NotAllowedError" || error.name === "SecurityError") {
    return "Camera permission was denied. Allow camera access in your browser settings and try again.";
  }
  if (error.name === "NotFoundError" || error.name === "OverconstrainedError") {
    return "No camera was found on this device.";
  }
  if (error.name === "NotReadableError") {
    return "The camera is in use by another app. Close it and try again.";
  }
  return "The camera could not be opened. Check the permission and try again.";
}

export default function CameraCapture({ onAccept, onClose }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const mounted = useRef(true);
  const [status, setStatus] = useState("starting");
  const [photo, setPhoto] = useState(null);
  const [message, setMessage] = useState("");

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  const startCamera = async () => {
    stopStream();
    setStatus("starting");
    setMessage("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("error");
      setMessage(cameraMessage({}));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      if (!mounted.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        try {
          await videoRef.current.play();
        } catch {
          // Autoplay can fail before the stream has a frame; the video still shows it.
        }
      }
      if (mounted.current) setStatus("live");
    } catch (error) {
      if (!mounted.current) return;
      setStatus("error");
      setMessage(cameraMessage(error));
    }
  };

  useEffect(() => {
    mounted.current = true;
    startCamera();
    return () => {
      mounted.current = false;
      stopStream();
    };
  }, []);

  useEffect(() => {
    if (!photo) return undefined;
    return () => URL.revokeObjectURL(photo.url);
  }, [photo]);

  const capture = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) {
      setMessage("The camera is not ready yet.");
      return;
    }
    const scale = Math.min(
      1,
      MAX_LONG_SIDE / Math.max(video.videoWidth, video.videoHeight),
    );
    const width = Math.round(video.videoWidth * scale);
    const height = Math.round(video.videoHeight * scale);
    const canvas = canvasRef.current;
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(video, 0, 0, width, height);
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setMessage("The photo could not be captured. Try again.");
          return;
        }
        stopStream();
        setPhoto({
          blob,
          url: URL.createObjectURL(blob),
          capturedAt: new Date(),
        });
        setStatus("preview");
      },
      "image/jpeg",
      JPEG_QUALITY,
    );
  };

  const retake = () => {
    setPhoto(null);
    startCamera();
  };

  const accept = () => {
    if (photo) onAccept(photo);
  };

  return (
    <div className="camera-backdrop">
      <div className="camera">
        <header className="camera-header">
          <span>Take a photo</span>
          <button
            type="button"
            className="panel-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        {status === "preview" && photo ? (
          <img className="camera-view" src={photo.url} alt="Captured photo" />
        ) : (
          <video
            ref={videoRef}
            className="camera-view"
            autoPlay
            playsInline
            muted
          />
        )}

        <canvas ref={canvasRef} hidden />

        <p className="camera-hint">
          Keep faces and number plates out of the photo.
        </p>

        {status === "starting" && <p className="camera-message">Opening camera…</p>}
        {status === "error" && <p className="camera-error">{message}</p>}
        {status === "preview" && message && (
          <p className="camera-error">{message}</p>
        )}

        <div className="camera-actions">
          {(status === "starting" || status === "live") && (
            <button
              type="button"
              className="auth-btn"
              onClick={capture}
              disabled={status !== "live"}
            >
              Capture
            </button>
          )}
          {status === "preview" && (
            <>
              <button type="button" className="auth-btn" onClick={retake}>
                Retake
              </button>
              <button type="button" className="auth-btn" onClick={accept}>
                Use photo
              </button>
            </>
          )}
          {status === "error" && (
            <button type="button" className="auth-btn" onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
