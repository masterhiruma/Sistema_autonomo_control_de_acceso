
import React, { useRef, useEffect, useState } from 'react';
import { VideoCameraIcon } from './icons/VideoCameraIcon';
import { ExclamationCircleIcon } from './icons/ExclamationCircleIcon';


const CameraFeed: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const getCameraStream = async () => {
      if (stream) return;
      try {
        const streamData = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user' },
          audio: false,
        });
        setStream(streamData);
        if (videoRef.current) {
          videoRef.current.srcObject = streamData;
        }
      } catch (err) {
        console.error("Error accessing camera:", err);
        setError("No se pudo acceder a la cámara. Verifique los permisos.");
      }
    };

    getCameraStream();

    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="bg-gray-800/50 rounded-xl shadow-2xl overflow-hidden aspect-video relative flex items-center justify-center border border-gray-700">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-cover transition-opacity duration-500 ${stream ? 'opacity-100' : 'opacity-0'}`}
      />
      {!stream && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
          <VideoCameraIcon className="h-16 w-16 mb-4 animate-pulse" />
          <p className="text-lg">Iniciando cámara...</p>
        </div>
      )}
      {error && (
         <div className="absolute inset-0 flex flex-col items-center justify-center text-red-400 bg-gray-800 p-4">
          <ExclamationCircleIcon className="h-16 w-16 mb-4" />
          <p className="text-lg text-center font-semibold">{error}</p>
        </div>
      )}
       <div className="absolute top-2 left-2 bg-red-600/80 text-white text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          REC
        </div>
    </div>
  );
};

export default CameraFeed;
