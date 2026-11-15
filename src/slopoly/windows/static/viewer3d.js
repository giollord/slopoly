// 3D viewer for builds and scenes (three.js): orbit camera, neutral studio light, and diagnostic overlays (wireframe,
// ground grid, origin axes, vertex normals, baked shade on/off). Palette textures are swapped without reloading the
// model. Used by view.html and review.html: create() returns a handle whose methods the page calls.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { VertexNormalsHelper } from "three/addons/helpers/VertexNormalsHelper.js";

const NORMAL_LENGTH = 0.03; // share of the model's bounding sphere radius

export function create(element, options = {}) {
    // preserve: keep the drawn frame so snapshot() can read it (review notes)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: !!options.preserve });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1;
    element.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(3, 5, 4);
    scene.add(sun);

    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 1000);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    const listeners = [];
    controls.addEventListener("change", () => { for (const f of listeners) f(); });

    const overlays = { wireframe: false, grid: false, axes: false, normals: false, shade: true };
    let model = null, helpers = [], palette = null, radius = 1, centre = new THREE.Vector3(), loadId = 0;
    const loader = new GLTFLoader();
    const textures = new THREE.TextureLoader();

    function resize() {
        const width = element.clientWidth, height = element.clientHeight;
        if (!width || !height) return;
        renderer.setSize(width, height, false);
        renderer.domElement.style.width = "100%";
        renderer.domElement.style.height = "100%";
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }
    const observer = new ResizeObserver(resize);
    observer.observe(element);

    let running = true;
    renderer.setAnimationLoop(() => {
        if (!running) return;
        controls.update();
        renderer.render(scene, camera);
    });

    function meshes() {
        const list = [];
        model?.traverse(o => { if (o.isMesh) list.push(o); });
        return list;
    }

    function clearHelpers() {
        for (const h of helpers) { h.removeFromParent(); h.geometry?.dispose(); h.material?.dispose?.(); }
        helpers = [];
    }

    function applyOverlays() {
        clearHelpers();
        if (overlays.grid) {
            const size = Math.max(2, Math.ceil(radius * 4));
            const grid = new THREE.GridHelper(size, size, 0x888888, 0x555555); // 1-metre cells
            scene.add(grid);
            helpers.push(grid);
        }
        if (overlays.axes) {
            const axes = new THREE.AxesHelper(Math.max(0.5, radius * 1.5)); // x red, y green, z blue
            axes.renderOrder = 1;
            scene.add(axes);
            helpers.push(axes);
        }
        for (const mesh of meshes()) {
            if (overlays.wireframe) {
                const lines = new THREE.LineSegments(new THREE.WireframeGeometry(mesh.geometry),
                    new THREE.LineBasicMaterial({ color: 0x111111, transparent: true, opacity: 0.6 }));
                mesh.add(lines);
                helpers.push(lines);
            }
            if (overlays.normals) {
                const normals = new VertexNormalsHelper(mesh, radius * NORMAL_LENGTH, 0x22aaff);
                scene.add(normals);
                helpers.push(normals);
            }
            for (const material of [mesh.material].flat()) {
                if (material.userData.vertexColors === undefined) material.userData.vertexColors = material.vertexColors;
                material.vertexColors = overlays.shade && material.userData.vertexColors;
                material.needsUpdate = true;
            }
        }
    }

    function frame() {
        const box = new THREE.Box3().setFromObject(model);
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        radius = Math.max(sphere.radius, 0.05);
        centre = sphere.center;
        const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.1;
        camera.position.copy(centre).add(new THREE.Vector3(1, 0.7, 1.3).normalize().multiplyScalar(distance));
        camera.near = distance / 100;
        camera.far = distance * 100;
        camera.updateProjectionMatrix();
        controls.target.copy(centre);
        controls.update();
    }

    async function setTexture(url) {
        if (!model || !url) return;
        const texture = await textures.loadAsync(url).catch(() => { throw new Error(`the palette ${url} could not be loaded`); });
        texture.flipY = false; // glTF UV convention
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.magFilter = texture.minFilter = THREE.NearestFilter; // keep palette cells crisp
        texture.generateMipmaps = false;
        for (const mesh of meshes())
            for (const material of [mesh.material].flat()) { material.map = texture; material.needsUpdate = true; }
    }

    return {
        async load(url, keepCamera) {
            const id = ++loadId;
            const gltf = await loader.loadAsync(url).catch(e => { throw new Error(`${url} could not be loaded: ${e?.message ?? e?.type ?? e}`); });
            if (id !== loadId) return; // a newer model was requested meanwhile
            const hadModel = !!model;
            if (model) { clearHelpers(); model.removeFromParent(); }
            model = gltf.scene;
            scene.add(model);
            if (!keepCamera || !hadModel) frame();
            else {
                const sphere = new THREE.Box3().setFromObject(model).getBoundingSphere(new THREE.Sphere());
                radius = Math.max(sphere.radius, 0.05);
            }
            applyOverlays();
            if (palette) await setTexture(palette);
        },
        setOverlays(values) { Object.assign(overlays, values); if (model) applyOverlays(); },
        // the orbit camera as plain numbers: {position, target, fov} (metres, degrees)
        getCamera() {
            return { position: camera.position.toArray(), target: controls.target.toArray(), fov: camera.fov };
        },
        setCamera(value) {
            camera.position.fromArray(value.position);
            controls.target.fromArray(value.target);
            if (value.fov) camera.fov = value.fov;
            const distance = camera.position.distanceTo(controls.target);
            camera.near = Math.max(distance / 100, 0.001);
            camera.far = distance * 100;
            camera.updateProjectionMatrix();
            controls.update();
        },
        onChange(listener) { listeners.push(listener); },
        setInteractive(on) { controls.enabled = on; },
        snapshot() { renderer.render(scene, camera); return renderer.domElement; },
        async setPalette(url) { palette = url; await setTexture(url); },
        resetView() { if (model) frame(); },
        dispose() {
            running = false;
            observer.disconnect();
            clearHelpers();
            controls.dispose();
            renderer.setAnimationLoop(null);
            renderer.dispose();
            pmrem.dispose();
            renderer.domElement.remove();
        },
    };
}
