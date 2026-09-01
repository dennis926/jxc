/**
 * 条形码扫描功能
 * 支持扫描枪和相机扫描
 */

var scannerStream = null;
var scannerCallback = null;
var scannerAnimationId = null;
var currentCamera = 'environment'; // 'environment' 后置, 'user' 前置

/**
 * 初始化扫描器
 * @param {function} callback - 扫描成功后的回调函数，参数为扫描结果
 */
function initScanner(callback) {
    scannerCallback = callback;
    var video = document.getElementById('scannerVideo');
    var canvas = document.getElementById('scannerCanvas');
    var status = document.getElementById('scannerStatus');
    
    if (!video || !canvas) {
        console.error('扫描器元素未找到');
        return;
    }
    
    // 检查浏览器支持
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        status.textContent = '您的浏览器不支持相机功能，请使用扫描枪或手动输入';
        status.className = 'mt-3 text-warning';
        return;
    }
    
    // 获取相机权限
    var constraints = {
        video: {
            facingMode: currentCamera,
            width: { ideal: 1280 },
            height: { ideal: 720 }
        }
    };
    
    navigator.mediaDevices.getUserMedia(constraints)
        .then(function(stream) {
            scannerStream = stream;
            video.srcObject = stream;
            status.textContent = '相机已启动，请将条形码对准扫描框';
            status.className = 'mt-3 text-success';
            
            // 开始扫描循环
            startScanLoop(video, canvas);
        })
        .catch(function(err) {
            console.error('相机启动失败:', err);
            status.textContent = '无法访问相机，请检查权限设置或使用扫描枪';
            status.className = 'mt-3 text-danger';
        });
    
    // 切换摄像头按钮
    var switchBtn = document.getElementById('switchCameraBtn');
    if (switchBtn) {
        switchBtn.onclick = function() {
            currentCamera = currentCamera === 'environment' ? 'user' : 'environment';
            stopScanner();
            setTimeout(function() {
                initScanner(callback);
            }, 300);
        };
    }
}

/**
 * 开始扫描循环
 */
function startScanLoop(video, canvas) {
    var ctx = canvas.getContext('2d');
    
    function scan() {
        if (!scannerStream) return;
        
        // 设置canvas尺寸
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        
        // 绘制视频帧
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // 尝试解码条形码
        try {
            var result = decodeBarcode(canvas, ctx);
            if (result && scannerCallback) {
                scannerCallback(result);
                return; // 扫描成功，停止循环
            }
        } catch (e) {
            // 解码失败，继续扫描
        }
        
        // 继续下一帧
        scannerAnimationId = requestAnimationFrame(scan);
    }
    
    // 等待视频准备好
    if (video.readyState >= 2) {
        scan();
    } else {
        video.onloadeddata = scan;
    }
}

/**
 * 解码条形码（使用简单的图像处理）
 * 注意：这是一个简化的实现，实际项目中建议使用专业的条形码库如 QuaggaJS 或 ZXing
 */
function decodeBarcode(canvas, ctx) {
    // 获取图像数据
    var width = canvas.width;
    var height = canvas.height;
    var imageData = ctx.getImageData(0, 0, width, height);
    var data = imageData.data;
    
    // 扫描中间区域（假设条形码在中间）
    var scanY = Math.floor(height / 2);
    var scanHeight = Math.floor(height * 0.2);
    var startY = scanY - scanHeight / 2;
    var endY = scanY + scanHeight / 2;
    
    // 简单的条形码检测逻辑
    // 实际项目中应该使用专业的条形码解码库
    // 这里提供一个占位符，建议集成 QuaggaJS
    
    return null; // 未检测到条形码
}

/**
 * 停止扫描器
 */
function stopScanner() {
    // 停止动画循环
    if (scannerAnimationId) {
        cancelAnimationFrame(scannerAnimationId);
        scannerAnimationId = null;
    }
    
    // 停止视频流
    if (scannerStream) {
        scannerStream.getTracks().forEach(function(track) {
            track.stop();
        });
        scannerStream = null;
    }
    
    var video = document.getElementById('scannerVideo');
    if (video) {
        video.srcObject = null;
    }
}

/**
 * 使用 QuaggaJS 进行扫描（推荐）
 * 需要先引入 QuaggaJS 库
 */
function initQuaggaScanner(callback) {
    if (typeof Quagga === 'undefined') {
        console.error('QuaggaJS 未加载，请引入库文件');
        // 降级到简单扫描
        initScanner(callback);
        return;
    }
    
    scannerCallback = callback;
    var status = document.getElementById('scannerStatus');
    
    Quagga.init({
        inputStream: {
            name: "Live",
            type: "LiveStream",
            target: document.querySelector('#scannerContainer'),
            constraints: {
                facingMode: currentCamera,
                width: { min: 640, ideal: 1280, max: 1920 },
                height: { min: 480, ideal: 720, max: 1080 }
            }
        },
        decoder: {
            readers: [
                "code_128_reader",
                "ean_reader",
                "ean_8_reader",
                "code_39_reader",
                "code_39_vin_reader",
                "codabar_reader",
                "upc_reader",
                "upc_e_reader",
                "i2of5_reader"
            ]
        },
        locate: true
    }, function(err) {
        if (err) {
            console.error('Quagga 初始化失败:', err);
            status.textContent = '扫描器初始化失败，请使用扫描枪';
            status.className = 'mt-3 text-danger';
            return;
        }
        
        status.textContent = '扫描器已就绪，请对准条形码';
        status.className = 'mt-3 text-success';
        Quagga.start();
    });
    
    // 检测到条形码
    Quagga.onDetected(function(result) {
        var code = result.codeResult.code;
        if (code && scannerCallback) {
            scannerCallback(code);
            Quagga.stop();
        }
    });
}

/**
 * 停止 Quagga 扫描
 */
function stopQuaggaScanner() {
    if (typeof Quagga !== 'undefined') {
        Quagga.stop();
    }
}

// 导出函数
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initScanner: initScanner,
        stopScanner: stopScanner,
        initQuaggaScanner: initQuaggaScanner,
        stopQuaggaScanner: stopQuaggaScanner
    };
}
