import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  VRM,
  VRMExpressionPresetName,
  VRMLoaderPlugin,
  VRMUtils,
} from "@pixiv/three-vrm";
import {
  createVRMAnimationClip,
  VRMAnimation,
  VRMAnimationLoaderPlugin,
  VRMLookAtQuaternionProxy,
} from "@pixiv/three-vrm-animation";

export type AvatarMotion = "idle" | "thinking";

type Props = {
  motion: AvatarMotion;
  speakingLevel: number;
  vrmExpected: boolean;
};

const animationUrls: Record<AvatarMotion, string> = {
  idle: "/animations/haihegirl_idle_6s.vrma",
  thinking: "/animations/haihegirl_thinking_4s.vrma",
};

const getVRMAnimation = (userData: Record<string, unknown>) => {
  const animations = userData.vrmAnimations as VRMAnimation[] | undefined;
  if (!animations?.[0]) throw new Error("VRMA 文件未包含可播放动画");
  return animations[0];
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
    let mixer: THREE.AnimationMixer | null = null;
    let activeMotion: AvatarMotion | null = null;
    let actions: Partial<Record<AvatarMotion, THREE.AnimationAction>> = {};
    let disposed = false;

    const activateMotion = (nextMotion: AvatarMotion, fadeDuration = 0.45) => {
      if (activeMotion === nextMotion) return;
      const nextAction = actions[nextMotion];
      if (!nextAction) return;

      const previousAction = activeMotion ? actions[activeMotion] : undefined;
      nextAction
        .reset()
        .setLoop(THREE.LoopRepeat, Infinity)
        .setEffectiveTimeScale(1)
        .setEffectiveWeight(1)
        .play();
      if (previousAction) previousAction.crossFadeTo(nextAction, fadeDuration, false);
      activeMotion = nextMotion;
    };

    const modelLoader = new GLTFLoader();
    modelLoader.register((parser) => new VRMLoaderPlugin(parser));
    const animationLoader = new GLTFLoader();
    animationLoader.register((parser) => new VRMAnimationLoaderPlugin(parser));

    const loadAvatar = async () => {
      try {
        const gltf = await modelLoader.loadAsync("/models/haihe-girl.vrm");
        const loadedVrm = gltf.userData.vrm as VRM;
        if (disposed) {
          VRMUtils.deepDispose(loadedVrm.scene);
          return;
        }

        if (loadedVrm.meta.metaVersion === "0") VRMUtils.rotateVRM0(loadedVrm);
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        // VRM 1.0 avatars face +Z. The camera is on +Z, and the source model remains untouched.
        loadedVrm.scene.rotation.y = 0;
        if (loadedVrm.lookAt) {
          loadedVrm.lookAt.target = lookTarget;
          const lookAtProxy = new VRMLookAtQuaternionProxy(loadedVrm.lookAt);
          lookAtProxy.name = "VRMLookAtQuaternionProxy";
          loadedVrm.scene.add(lookAtProxy);
        }
        scene.add(loadedVrm.scene);
        vrm = loadedVrm;

        const loadedAnimations = await Promise.all(
          (Object.entries(animationUrls) as [AvatarMotion, string][]).map(
            async ([name, url]) => {
              const animationGltf = await animationLoader.loadAsync(url);
              return [name, getVRMAnimation(animationGltf.userData)] as const;
            },
          ),
        );
        if (disposed) return;

        mixer = new THREE.AnimationMixer(loadedVrm.scene);
        actions = Object.fromEntries(
          loadedAnimations.map(([name, animation]) => [
            name,
            mixer?.clipAction(createVRMAnimationClip(animation, loadedVrm)),
          ]),
        );
        activateMotion(motionRef.current, 0);
        setState("ready");
      } catch {
        if (!disposed) setState("placeholder");
      }
    };
    void loadAvatar();

    const pointer = new THREE.Vector2();
    const onPointerMove = (event: PointerEvent) => {
      const rect = mount.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
      lookTarget.position.set(pointer.x * 0.34, 1.46 + pointer.y * 0.2, 2.8);
    };
    mount.addEventListener("pointermove", onPointerMove);

    const clock = new THREE.Clock();
    let animationFrame = 0;
    const render = () => {
      animationFrame = requestAnimationFrame(render);
      const delta = Math.min(clock.getDelta(), 0.05);
      if (vrm) {
        activateMotion(motionRef.current);
        mixer?.update(delta);
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
      cancelAnimationFrame(animationFrame);
      mount.removeEventListener("pointermove", onPointerMove);
      mixer?.stopAllAction();
      actions = {};
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
            <span>{state === "loading" ? "正在载入模型与动作" : "模型暂未载入"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
