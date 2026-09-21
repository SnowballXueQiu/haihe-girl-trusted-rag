import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  VRM,
  VRMExpressionPresetName,
  VRMHumanBoneName,
  VRMLoaderPlugin,
  VRMUtils,
} from "@pixiv/three-vrm";

type Props = {
  motion: "idle" | "thinking";
  speakingLevel: number;
  vrmExpected: boolean;
};

const motionBones = [
  VRMHumanBoneName.Hips,
  VRMHumanBoneName.Spine,
  VRMHumanBoneName.Chest,
  VRMHumanBoneName.Neck,
  VRMHumanBoneName.Head,
  VRMHumanBoneName.LeftUpperArm,
  VRMHumanBoneName.LeftLowerArm,
  VRMHumanBoneName.LeftHand,
  VRMHumanBoneName.RightUpperArm,
  VRMHumanBoneName.RightLowerArm,
  VRMHumanBoneName.RightHand,
  VRMHumanBoneName.LeftUpperLeg,
  VRMHumanBoneName.RightUpperLeg,
] as const;

type MotionBone = (typeof motionBones)[number];
type EulerTuple = readonly [x: number, y: number, z: number];
type MotionPose = Record<MotionBone, EulerTuple>;

const idlePose: MotionPose = {
  [VRMHumanBoneName.Hips]: [0, 0, 0],
  [VRMHumanBoneName.Spine]: [0.018, 0, -0.015],
  [VRMHumanBoneName.Chest]: [-0.012, 0, 0.018],
  [VRMHumanBoneName.Neck]: [0, 0.015, -0.018],
  [VRMHumanBoneName.Head]: [0, -0.018, 0.018],
  [VRMHumanBoneName.LeftUpperArm]: [0.1, 0.22, -0.84],
  [VRMHumanBoneName.LeftLowerArm]: [0.03, 0.12, -1.12],
  [VRMHumanBoneName.LeftHand]: [0.02, 0, -0.12],
  [VRMHumanBoneName.RightUpperArm]: [-0.1, -0.22, 0.84],
  [VRMHumanBoneName.RightLowerArm]: [-0.03, -0.12, 1.12],
  [VRMHumanBoneName.RightHand]: [-0.02, 0, 0.12],
  [VRMHumanBoneName.LeftUpperLeg]: [0, 0, -0.018],
  [VRMHumanBoneName.RightUpperLeg]: [0, 0, 0.018],
};

const thinkingPose: MotionPose = {
  ...idlePose,
  [VRMHumanBoneName.Hips]: [0, -0.012, 0.025],
  [VRMHumanBoneName.Spine]: [0.03, -0.018, 0.02],
  [VRMHumanBoneName.Chest]: [0.015, -0.03, 0.045],
  [VRMHumanBoneName.Neck]: [-0.025, 0.055, 0.065],
  [VRMHumanBoneName.Head]: [-0.045, 0.095, 0.105],
};

export function AvatarStage({ motion, speakingLevel, vrmExpected }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const levelRef = useRef(speakingLevel);
  const motionRef = useRef(motion);
  const [state, setState] = useState<"loading" | "ready" | "placeholder">("loading");

  useEffect(() => {
    levelRef.current = speakingLevel;
  }, [speakingLevel]);

  useEffect(() => {
    motionRef.current = motion;
  }, [motion]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    if (!vrmExpected) {
      setState("placeholder");
      return;
    }

    setState("loading");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
    camera.position.set(0, 1.28, 2.05);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xfffdf8, 0x7d8581, 1.18));
    const key = new THREE.DirectionalLight(0xfff7ef, 1.62);
    key.position.set(1.8, 3.2, 2.8);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xe3f0ed, 0.28);
    rim.position.set(-2.5, 1.8, -1.5);
    scene.add(rim);

    const lookTarget = new THREE.Object3D();
    lookTarget.position.set(0, 1.45, 2.8);
    scene.add(lookTarget);

    let vrm: VRM | null = null;
    let motionBoneNodes: Partial<Record<MotionBone, THREE.Object3D>> = {};
    let hipsRestPosition: THREE.Vector3 | null = null;
    let disposed = false;
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    loader.load(
      "/models/haihe-girl.vrm",
      (gltf) => {
        if (disposed) return;
        vrm = gltf.userData.vrm as VRM;
        if (vrm.meta.metaVersion === "0") VRMUtils.rotateVRM0(vrm);
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        // VRM 1.0 avatars face +Z. The camera is placed on +Z, so no 180° turn is needed.
        // Keep animation in runtime only; the supplied VRM file is never rewritten.
        vrm.scene.rotation.y = 0;
        motionBoneNodes = Object.fromEntries(
          motionBones.map((boneName) => [
            boneName,
            vrm?.humanoid.getNormalizedBoneNode(boneName) ?? undefined,
          ]),
        ) as Partial<Record<MotionBone, THREE.Object3D>>;
        hipsRestPosition = motionBoneNodes[VRMHumanBoneName.Hips]?.position.clone() ?? null;
        if (vrm.lookAt) vrm.lookAt.target = lookTarget;
        scene.add(vrm.scene);
        setState("ready");
      },
      undefined,
      () => {
        if (!disposed) setState("placeholder");
      },
    );

    const pointer = new THREE.Vector2();
    const onPointerMove = (event: PointerEvent) => {
      const rect = mount.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
    };
    mount.addEventListener("pointermove", onPointerMove);

    const clock = new THREE.Clock();
    let motionBlend = motionRef.current === "thinking" ? 1 : 0;
    let animation = 0;
    const render = () => {
      animation = requestAnimationFrame(render);
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      if (vrm) {
        motionBlend = THREE.MathUtils.damp(
          motionBlend,
          motionRef.current === "thinking" ? 1 : 0,
          5.5,
          delta,
        );
        lookTarget.position.set(
          pointer.x * 0.34 + motionBlend * 0.08,
          1.46 + pointer.y * 0.2 + motionBlend * 0.08,
          2.8,
        );

        for (const boneName of motionBones) {
          const bone = motionBoneNodes[boneName];
          if (!bone) continue;
          const from = idlePose[boneName];
          const to = thinkingPose[boneName];
          bone.rotation.set(
            THREE.MathUtils.lerp(from[0], to[0], motionBlend),
            THREE.MathUtils.lerp(from[1], to[1], motionBlend),
            THREE.MathUtils.lerp(from[2], to[2], motionBlend),
          );
        }

        const hips = motionBoneNodes[VRMHumanBoneName.Hips];
        if (hips && hipsRestPosition) {
          hips.position.set(
            hipsRestPosition.x + motionBlend * 0.015,
            hipsRestPosition.y + Math.sin(elapsed * 1.15) * 0.004,
            hipsRestPosition.z,
          );
        }

        const spine = motionBoneNodes[VRMHumanBoneName.Spine];
        const chest = motionBoneNodes[VRMHumanBoneName.Chest];
        const head = motionBoneNodes[VRMHumanBoneName.Head];
        if (spine) spine.rotation.z += Math.sin(elapsed * 0.62) * 0.01;
        if (chest) chest.rotation.x += Math.sin(elapsed * 1.35) * 0.009;
        if (head) head.rotation.y += motionBlend * Math.sin(elapsed * 0.72) * 0.018;
        const blinkCycle = elapsed % 4.8;
        const blink = blinkCycle > 4.48 ? Math.sin(((blinkCycle - 4.48) / 0.32) * Math.PI) : 0;
        vrm.expressionManager?.setValue(VRMExpressionPresetName.Blink, blink);
        vrm.expressionManager?.setValue(
          VRMExpressionPresetName.Aa,
          Math.min(0.88, levelRef.current * 0.92),
        );
        vrm.update(delta);
      }
      renderer.render(scene, camera);
    };

    const resize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();
    render();

    return () => {
      disposed = true;
      observer.disconnect();
      cancelAnimationFrame(animation);
      mount.removeEventListener("pointermove", onPointerMove);
      renderer.dispose();
      renderer.domElement.remove();
      if (vrm) VRMUtils.deepDispose(vrm.scene);
    };
  }, [vrmExpected]);

  return (
    <div className="avatar-stage" ref={mountRef} aria-label="海河少女三维角色舞台">
      {state !== "ready" && (
        <div className="avatar-placeholder" aria-live="polite">
          <div className="avatar-halo" />
          <img src="/avatar-placeholder.jpg" alt="海河少女角色参考形象" />
          <div className={`placeholder-mouth ${speakingLevel > 0.08 ? "is-speaking" : ""}`} />
          <div className="model-note">
            <span>{state === "loading" ? "正在载入模型" : "模型暂未载入"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
