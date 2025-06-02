<template>
  <div class="memory-timeline-3d">
    <div ref="container" class="webgl-container"></div>
    <div v-if="loading" class="loading-overlay">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { ElIcon } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import * as TWEEN from '@tweenjs/tween.js';

const props = defineProps({
  memories: {
    type: Array,
    required: true
  },
  selectedMemory: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['select-memory']);

// 引用DOM元素
const container = ref(null);

// 场景相关变量
let scene, camera, renderer, controls;
let memoryObjects = [];
let raycaster = new THREE.Raycaster();
let mouse = new THREE.Vector2();
let animationId = null;

// 记忆时间排序及分组
const getTimelineData = () => {
  // 按时间排序
  const sorted = [...props.memories].sort((a, b) => a.created_at - b.created_at);
  
  // 计算时间范围
  if (sorted.length === 0) return { sorted, minTime: 0, maxTime: 0, timeRange: 0 };
  
  const minTime = sorted[0].created_at;
  const maxTime = sorted[sorted.length - 1].created_at;
  const timeRange = maxTime - minTime;
  
  return { sorted, minTime, maxTime, timeRange };
};

// 初始化3D场景
const initScene = () => {
  // 创建场景
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf0f2f5);
  
  // 创建相机
  camera = new THREE.PerspectiveCamera(75, container.value.clientWidth / container.value.clientHeight, 0.1, 1000);
  camera.position.set(0, 5, 10);
  
  // 创建渲染器
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(container.value.clientWidth, container.value.clientHeight);
  renderer.shadowMap.enabled = true;
  container.value.appendChild(renderer.domElement);
  
  // 添加控制器
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  
  // 添加光源
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambientLight);
  
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
  directionalLight.position.set(10, 20, 10);
  directionalLight.castShadow = true;
  scene.add(directionalLight);
  
  // 添加时间轴
  addTimeline();
  
  // 添加事件监听器
  window.addEventListener('resize', onWindowResize);
  renderer.domElement.addEventListener('click', onMouseClick);
  
  // 启动动画循环
  animate();
};

// 添加时间轴基础线
const addTimeline = () => {
  const timelineGeometry = new THREE.BufferGeometry();
  const lineMaterial = new THREE.LineBasicMaterial({ color: 0x666666 });
  
  const points = [];
  points.push(new THREE.Vector3(-50, 0, 0));
  points.push(new THREE.Vector3(50, 0, 0));
  
  timelineGeometry.setFromPoints(points);
  const timeline = new THREE.Line(timelineGeometry, lineMaterial);
  scene.add(timeline);
  
  // 添加刻度线
  for (let i = -50; i <= 50; i += 5) {
    const tickGeometry = new THREE.BufferGeometry();
    const tickPoints = [];
    tickPoints.push(new THREE.Vector3(i, 0, 0));
    tickPoints.push(new THREE.Vector3(i, 0.5, 0));
    
    tickGeometry.setFromPoints(tickPoints);
    const tick = new THREE.Line(tickGeometry, lineMaterial);
    scene.add(tick);
  }
};

// 更新记忆可视化
const updateMemoryObjects = () => {
  // 清除现有记忆对象
  memoryObjects.forEach(obj => {
    scene.remove(obj);
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) obj.material.dispose();
  });
  memoryObjects = [];
  
  // 获取时间线数据
  const { sorted, minTime, maxTime, timeRange } = getTimelineData();
  if (sorted.length === 0) return;
  
  // 创建新的记忆对象
  sorted.forEach((memory, index) => {
    // 计算时间轴上的位置
    const timePosition = timeRange ? -40 + ((memory.created_at - minTime) / timeRange) * 80 : 0;
    
    // 根据记忆的权重决定大小
    const size = memory.weight ? 0.3 + memory.weight * 0.5 : 0.5;
    
    // 创建记忆球体
    const geometry = new THREE.SphereGeometry(size, 32, 32);
    
    // 根据记忆类型决定颜色
    let color = 0x3498db; // 默认蓝色
    
    if (memory.is_permanent) {
      color = 0xe74c3c; // 永久记忆红色
    }
    
    // 如果是当前选中的记忆，使用高亮颜色
    if (props.selectedMemory && props.selectedMemory.id === memory.id) {
      color = 0xf39c12; // 选中黄色
    }
    
    const material = new THREE.MeshStandardMaterial({ 
      color: color,
      metalness: 0.3,
      roughness: 0.4,
    });
    
    const sphere = new THREE.Mesh(geometry, material);
    sphere.position.set(timePosition, size, 0);
    sphere.castShadow = true;
    sphere.receiveShadow = true;
    
    // 存储记忆数据，用于点击交互
    sphere.userData = { memory, index };
    
    scene.add(sphere);
    memoryObjects.push(sphere);
    
    // 添加连接线
    const lineGeometry = new THREE.BufferGeometry();
    const points = [];
    points.push(new THREE.Vector3(timePosition, 0, 0));
    points.push(new THREE.Vector3(timePosition, size, 0));
    
    lineGeometry.setFromPoints(points);
    const line = new THREE.Line(
      lineGeometry,
      new THREE.LineBasicMaterial({ color: 0x999999 })
    );
    scene.add(line);
    memoryObjects.push(line);
  });
};

// 点击事件处理
const onMouseClick = (event) => {
  // 计算鼠标在归一化设备坐标中的位置
  mouse.x = (event.clientX - container.value.getBoundingClientRect().left) / container.value.clientWidth * 2 - 1;
  mouse.y = -((event.clientY - container.value.getBoundingClientRect().top) / container.value.clientHeight) * 2 + 1;
  
  // 从相机通过鼠标位置发射射线
  raycaster.setFromCamera(mouse, camera);
  
  // 检查射线是否与记忆对象相交
  const intersects = raycaster.intersectObjects(memoryObjects.filter(obj => obj.type === 'Mesh'));
  
  if (intersects.length > 0) {
    const selectedObject = intersects[0].object;
    if (selectedObject.userData && selectedObject.userData.memory) {
      // 发出选中记忆事件
      emit('select-memory', selectedObject.userData.memory);
      
      // 动画效果 - 放大选中的记忆球体
      new TWEEN.Tween(selectedObject.scale)
        .to({ x: 1.2, y: 1.2, z: 1.2 }, 200)
        .easing(TWEEN.Easing.Cubic.Out)
        .start()
        .onComplete(() => {
          // 恢复原始大小
          new TWEEN.Tween(selectedObject.scale)
            .to({ x: 1, y: 1, z: 1 }, 200)
            .easing(TWEEN.Easing.Cubic.In)
            .start();
        });
    }
  }
};

// 窗口大小调整处理
const onWindowResize = () => {
  camera.aspect = container.value.clientWidth / container.value.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.value.clientWidth, container.value.clientHeight);
};

// 动画循环
const animate = () => {
  animationId = requestAnimationFrame(animate);
  controls.update();
  TWEEN.update();
  renderer.render(scene, camera);
};

// 当记忆数据变化时，更新可视化
watch(() => props.memories, () => {
  if (scene) {
    updateMemoryObjects();
  }
}, { deep: true });

// 当选中的记忆变化时，更新高亮显示
watch(() => props.selectedMemory, () => {
  if (scene) {
    updateMemoryObjects();
  }
});

// 组件挂载时初始化
onMounted(() => {
  initScene();
  updateMemoryObjects();
});

// 组件卸载前清理资源
onBeforeUnmount(() => {
  if (animationId) {
    cancelAnimationFrame(animationId);
  }
  
  window.removeEventListener('resize', onWindowResize);
  
  if (renderer && renderer.domElement) {
    renderer.domElement.removeEventListener('click', onMouseClick);
    container.value.removeChild(renderer.domElement);
  }
  
  // 清理场景资源
  if (scene) {
    scene.traverse((object) => {
      if (object.geometry) object.geometry.dispose();
      if (object.material) {
        if (Array.isArray(object.material)) {
          object.material.forEach(material => material.dispose());
        } else {
          object.material.dispose();
        }
      }
    });
    
    renderer.dispose();
    scene = null;
    camera = null;
    renderer = null;
    controls = null;
  }
});
</script>

<style scoped>
.memory-timeline-3d {
  position: relative;
  width: 100%;
  height: 100%;
}

.webgl-container {
  width: 100%;
  height: 100%;
  background-color: #f0f2f5;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.7);
  z-index: 10;
}

.loading-icon {
  font-size: 48px;
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style> 