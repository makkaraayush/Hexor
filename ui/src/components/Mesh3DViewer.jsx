import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RotateCw, Eye, ShieldCheck, AlertTriangle, Layers, Ruler } from 'lucide-react';

export default function Mesh3DViewer({ 
  stlUrl, 
  meshAnalysis = null,
  modelName = "3D Mesh Model",
  height = "240px",
  onClose = null 
}) {
  const canvasMountRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [isWireframe, setIsWireframe] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const meshMaterialRef = useRef(null);
  const controlsRef = useRef(null);
  const cameraRef = useRef(null);
  const initialCamPos = useRef(new THREE.Vector3(0, -280, 220));

  useEffect(() => {
    const mount = canvasMountRef.current;
    if (!mount || !stlUrl) return;

    setLoading(true);
    setLoadError(null);

    // Safely clear any previous canvas elements created by earlier runs
    while (mount.firstChild) {
      mount.removeChild(mount.firstChild);
    }

    const width = mount.clientWidth || 300;
    const heightPx = mount.clientHeight || 240;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060b13);
    scene.fog = new THREE.FogExp2(0x060b13, 0.002);

    // Camera setup - Z is UP (matching 3D printing & CAD build plate convention)
    const camera = new THREE.PerspectiveCamera(45, Math.max(1, width) / Math.max(1, heightPx), 1, 2000);
    camera.up.set(0, 0, 1);
    camera.position.copy(initialCamPos.current);
    cameraRef.current = camera;

    // WebGL Renderer
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
      renderer.setSize(width, heightPx);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      mount.appendChild(renderer.domElement);
    } catch (e) {
      console.error("WebGL initialization failed:", e);
      setLoadError("WebGL unavailable on this device.");
      setLoading(false);
      return;
    }

    // Orbit Controls (configured for Z-up)
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 2.0;
    controls.maxPolarAngle = Math.PI / 2 - 0.02; // Restrict camera from going underneath horizontal bed
    controls.minDistance = 30;
    controls.maxDistance = 600;
    controls.target.set(0, 0, 30);
    controls.update();
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x406080, 2.0);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0x00f0ff, 2.5);
    keyLight.position.set(150, -200, 250);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x10b981, 1.2);
    fillLight.position.set(-150, 150, 150);
    scene.add(fillLight);

    const topLight = new THREE.PointLight(0xffffff, 1.5, 600);
    topLight.position.set(0, 0, 250);
    scene.add(topLight);

    // Bambu Lab A1 Build Plate Simulation (256mm x 256mm lying FLAT on horizontal XY plane)
    const plateSize = 256;
    const plateGeo = new THREE.BoxGeometry(plateSize, plateSize, 2);
    const plateMat = new THREE.MeshStandardMaterial({
      color: 0x141a24,
      roughness: 0.85,
      metalness: 0.2
    });
    const plate = new THREE.Mesh(plateGeo, plateMat);
    plate.position.set(0, 0, -1.0); // Top face at exactly Z = 0
    scene.add(plate);

    // Build Plate Grid (Flat in XY)
    const grid = new THREE.GridHelper(plateSize, 16, 0x00f0ff, 0x1a3344);
    grid.rotation.x = Math.PI / 2;
    grid.position.set(0, 0, 0.05); // Just above Z = 0 to prevent z-fighting
    scene.add(grid);

    // Bed Boundary Lines (256x256mm horizontal boundary outline)
    const borderPoints = [
      new THREE.Vector3(-128, -128, 0.2),
      new THREE.Vector3(128, -128, 0.2),
      new THREE.Vector3(128, 128, 0.2),
      new THREE.Vector3(-128, 128, 0.2),
      new THREE.Vector3(-128, -128, 0.2)
    ];
    const borderGeo = new THREE.BufferGeometry().setFromPoints(borderPoints);
    const borderMat = new THREE.LineBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.8 });
    scene.add(new THREE.Line(borderGeo, borderMat));

    // Mesh Material
    const mat = new THREE.MeshStandardMaterial({
      color: 0x00e5ff,
      metalness: 0.35,
      roughness: 0.35,
      wireframe: isWireframe
    });
    meshMaterialRef.current = mat;

    // Load STL Geometry
    let isDisposed = false;
    const loader = new STLLoader();

    loader.load(
      stlUrl,
      (geometry) => {
        if (isDisposed) {
          geometry.dispose();
          return;
        }
        try {
          geometry.computeVertexNormals();
          geometry.center();
          geometry.computeBoundingBox();
          const bbox = geometry.boundingBox;
          const zOffset = bbox ? -bbox.min.z : 0;

          const mesh = new THREE.Mesh(geometry, mat);
          mesh.position.set(0, 0, zOffset);
          scene.add(mesh);

          if (bbox) {
            const modelHeight = bbox.max.z - bbox.min.z;
            controls.target.set(0, 0, modelHeight / 2);
            controls.update();
          }
          setLoading(false);
        } catch (e) {
          console.error("Error setting up geometry:", e);
          setLoadError("Failed to render 3D geometry.");
          setLoading(false);
        }
      },
      undefined,
      (err) => {
        if (isDisposed) return;
        console.error("Error loading STL:", err);
        setLoadError("Failed to parse 3D mesh.");
        setLoading(false);
      }
    );

    // Animation Loop
    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!mount || !renderer || !camera) return;
      const w = mount.clientWidth || 300;
      const h = mount.clientHeight || 240;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      isDisposed = true;
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      if (renderer) {
        if (renderer.domElement && renderer.domElement.parentNode === mount) {
          mount.removeChild(renderer.domElement);
        }
        renderer.dispose();
      }
      plateGeo.dispose();
      plateMat.dispose();
      borderGeo.dispose();
      borderMat.dispose();
      grid.dispose();
      mat.dispose();
    };
  }, [stlUrl]);

  // Wireframe sync
  useEffect(() => {
    if (meshMaterialRef.current) {
      meshMaterialRef.current.wireframe = isWireframe;
      meshMaterialRef.current.needsUpdate = true;
    }
  }, [isWireframe]);

  // Auto-rotate sync
  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
    }
  }, [autoRotate]);

  const resetCamera = () => {
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.up.set(0, 0, 1);
      cameraRef.current.position.copy(initialCamPos.current);
      controlsRef.current.target.set(0, 0, 30);
      controlsRef.current.update();
    }
  };

  const dims = meshAnalysis?.dimensions_mm || { width_x: 60, depth_y: 75, height_z: 75 };
  const mass = meshAnalysis?.estimated_mass_grams || 45;
  const overhang = meshAnalysis?.overhang_percentage ?? 4.2;
  const supports = meshAnalysis?.supports_recommended ?? false;
  const fits = meshAnalysis?.fits_bambu_a1 ?? true;

  return (
    <div className="relative flex flex-col bg-slate-950/90 border border-cyan-500/40 rounded-xl overflow-hidden shadow-[0_0_20px_rgba(0,240,255,0.15)]">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-cyan-950/50 border-b border-cyan-500/20 backdrop-blur-md">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span className="font-orbitron font-semibold text-xs tracking-wider text-cyan-200 truncate max-w-[200px]">
            {modelName}
          </span>
          <span className="text-[10px] font-mono-tech px-1.5 py-0.5 rounded bg-cyan-900/60 text-cyan-300 border border-cyan-500/30">
            3D MESH
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-1.5">
          <button
            onClick={() => setAutoRotate(!autoRotate)}
            className={`p-1 rounded text-xs transition-colors ${autoRotate ? 'bg-cyan-500/30 text-cyan-200 border border-cyan-400/60' : 'bg-black/40 text-cyan-600 hover:text-cyan-300'}`}
            title="Toggle Auto-Rotation"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsWireframe(!isWireframe)}
            className={`p-1 rounded text-xs transition-colors ${isWireframe ? 'bg-amber-500/30 text-amber-200 border border-amber-400/60' : 'bg-black/40 text-cyan-600 hover:text-cyan-300'}`}
            title="Toggle Wireframe"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={resetCamera}
            className="p-1 rounded bg-black/40 text-cyan-600 hover:text-cyan-300 text-xs transition-colors"
            title="Reset Camera"
          >
            <Ruler className="w-3.5 h-3.5" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded bg-red-950/40 border border-red-500/40 text-red-300 hover:bg-red-900/50 text-xs"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* WebGL Canvas Outer Frame */}
      <div 
        style={{ height }}
        className="relative w-full bg-gradient-to-b from-[#060b13] to-[#04070c] overflow-hidden"
      >
        {/* Dedicated WebGL Container with ZERO React children to prevent any removeChild DOM crashes */}
        <div 
          ref={canvasMountRef} 
          className="w-full h-full cursor-grab active:cursor-grabbing" 
        />

        {/* Overlays rendered as React SIBLINGS */}
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm z-10 text-cyan-400 font-mono-tech text-xs space-y-2 pointer-events-none">
            <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            <span>Analyzing & Rendering 3D Geometry...</span>
          </div>
        )}

        {loadError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10 text-red-400 font-mono-tech text-xs p-4 text-center pointer-events-none">
            <AlertTriangle className="w-6 h-6 mb-2 text-red-400" />
            <span>{loadError}</span>
          </div>
        )}

        {/* Orbit hint pill */}
        <div className="absolute bottom-2 left-2 pointer-events-none bg-black/70 border border-cyan-500/30 rounded px-2 py-0.5 text-[9px] font-mono-tech text-cyan-400/80 backdrop-blur-sm">
          Drag to rotate • Scroll to zoom
        </div>

        {/* Bed Fit Badge */}
        <div className="absolute top-2 right-2 pointer-events-none">
          {fits ? (
            <div className="flex items-center space-x-1 bg-emerald-950/80 border border-emerald-500/50 rounded px-2 py-0.5 text-[10px] font-mono-tech text-emerald-300 backdrop-blur-sm">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              <span>Bambu A1 Bed (256mm) OK</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1 bg-red-950/80 border border-red-500/50 rounded px-2 py-0.5 text-[10px] font-mono-tech text-red-300 backdrop-blur-sm">
              <AlertTriangle className="w-3 h-3 text-red-400" />
              <span>Exceeds 256mm Bed</span>
            </div>
          )}
        </div>
      </div>

      {/* Structural Metrics Footer */}
      <div className="grid grid-cols-4 gap-1 p-2 bg-cyan-950/40 border-t border-cyan-500/20 text-[10px] font-mono-tech">
        <div className="bg-black/40 rounded p-1 border border-cyan-500/10">
          <span className="text-cyan-500 block">DIMENSIONS</span>
          <span className="text-cyan-200 font-semibold">{dims.width_x}×{dims.depth_y}×{dims.height_z}mm</span>
        </div>
        <div className="bg-black/40 rounded p-1 border border-cyan-500/10">
          <span className="text-cyan-500 block">MASS / VOL</span>
          <span className="text-amber-300 font-semibold">~{mass}g ({meshAnalysis?.volume_cm3 || 25}cm³)</span>
        </div>
        <div className="bg-black/40 rounded p-1 border border-cyan-500/10">
          <span className="text-cyan-500 block">OVERHANGS</span>
          <span className={`${overhang > 4 ? 'text-amber-300' : 'text-emerald-300'} font-semibold`}>
            {overhang}% {supports ? '(Tree Sup)' : '(Clean)'}
          </span>
        </div>
        <div className="bg-black/40 rounded p-1 border border-cyan-500/10">
          <span className="text-cyan-500 block">EST. TIME</span>
          <span className="text-emerald-400 font-semibold">
            {meshAnalysis?.bambu_a1_slicing?.estimated_print_time_formatted || "45m"}
          </span>
        </div>
      </div>
    </div>
  );
}
