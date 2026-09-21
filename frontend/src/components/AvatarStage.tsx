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
  speakingLevel: number;
  vrmExpected: boolean;
};

const idleBones = [
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

type IdleBone = (typeof idleBones)[number];
type EulerTuple = readonly [x: number, y: number, z: number];
type IdlePose = Record<IdleBone, EulerTuple>;

// “Standby 7”：双手轻收于身后，重心稳定，适合作为文化讲解的主待机姿态。
const standbySeven: IdlePose = {
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

// “Standby 5”：侧身歪头并抬手致意，保留截图中更活泼的轮廓。
const standbyFive: IdlePose = {
  [VRMHumanBoneName.Hips]: [0, -0.02, 0.085],
  [VRMHumanBoneName.Spine]: [0.025, -0.025, 0.105],
  [VRMHumanBoneName.Chest]: [0.025, -0.045, 0.14],
  [VRMHumanBoneName.Neck]: [-0.025, 0.045, 0.12],
  [VRMHumanBoneName.Head]: [-0.035, 0.07, 0.17],
  [VRMHumanBoneName.LeftUpperArm]: [0.04, 0.1, -0.92],
  [VRMHumanBoneName.LeftLowerArm]: [0.02, 0.04, -0.35],
  [VRMHumanBoneName.LeftHand]: [0.02, 0, -0.08],
  [VRMHumanBoneName.RightUpperArm]: [-0.12, 0.2, -0.82],
  [VRMHumanBoneName.RightLowerArm]: [-0.08, -0.16, -2.06],
  [VRMHumanBoneName.RightHand]: [0.03, 0.08, 0.2],
  [VRMHumanBoneName.LeftUpperLeg]: [0, 0, 0.035],
  [VRMHumanBoneName.RightUpperLeg]: [0, 0, 0.075],
};

const smoothstep = (value: number) => {
  const t = THREE.MathUtils.clamp(value, 0, 1);
  return t * t * (3 - 2 * t);
};

const standbyBlendAt = (elapsed: number) => {
  const phase = elapsed % 15.8;
  if (phase < 5.2) return 0;
  if (phase < 6.6) return smoothstep((phase - 5.2) / 1.4);
  if (phase < 12) return 1;
  if (phase < 13.4) return 1 - smoothstep((phase - 12) / 1.4);
  return 0;
};

export function AvatarStage({ speakingLevel, vrmExpected }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const levelRef = useRef(speakingLevel);
  const [state, setState] = useState<"loading" | "ready" | "placeholder">("loading");

  useEffect(() => {
    levelRef.current = speakingLevel;
  }, [speakingLevel]);

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
    let idleBoneNodes: Partial<Record<IdleBone, THREE.Object3D>> = {};
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
        idleBoneNodes = Object.fromEntries(
          idleBones.map((boneName) => [
            boneName,
            vrm?.humanoid.getNormalizedBoneNode(boneName) ?? undefined,
          ]),
        ) as Partial<Record<IdleBone, THREE.Object3D>>;
        hipsRestPosition = idleBoneNodes[VRMHumanBoneName.Hips]?.position.clone() ?? null;
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
      lookTarget.position.set(pointer.x * 0.34, 1.46 + pointer.y * 0.2, 2.8);
    };
    mount.addEventListener("pointermove", onPointerMove);

    const clock = new THREE.Clock();
    let animation = 0;
    const render = () => {
      animation = requestAnimationFrame(render);
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      if (vrm) {
        const standbyBlend = standbyBlendAt(elapsed);
        camera.position.z = THREE.MathUtils.lerp(2.05, 2.23, standbyBlend);
        for (const boneName of idleBones) {
          const bone = idleBoneNodes[boneName];
          if (!bone) continue;
          const from = standbySeven[boneName];
          const to = standbyFive[boneName];
          bone.rotation.set(
            THREE.MathUtils.lerp(from[0], to[0], standbyBlend),
            THREE.MathUtils.lerp(from[1], to[1], standbyBlend),
            THREE.MathUtils.lerp(from[2], to[2], standbyBlend),
          );
        }

        const hips = idleBoneNodes[VRMHumanBoneName.Hips];
        if (hips && hipsRestPosition) {
          hips.position.set(
            hipsRestPosition.x + standbyBlend * 0.045,
            hipsRestPosition.y + Math.sin(elapsed * 1.15) * 0.004,
            hipsRestPosition.z,
          );
        }

        const spine = idleBoneNodes[VRMHumanBoneName.Spine];
        const chest = idleBoneNodes[VRMHumanBoneName.Chest];
        if (spine) spine.rotation.z += Math.sin(elapsed * 0.62) * 0.01;
        if (chest) chest.rotation.x += Math.sin(elapsed * 1.35) * 0.009;
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
