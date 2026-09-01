/**
 * 进销存管理系统 - 前端交互脚本
 */

document.addEventListener('DOMContentLoaded', function () {

    // ===== 侧边栏折叠切换 =====
    var menuToggle = document.getElementById('menu-toggle');
    var wrapper = document.getElementById('wrapper');

    if (menuToggle && wrapper) {
        menuToggle.addEventListener('click', function (e) {
            e.preventDefault();
            wrapper.classList.toggle('toggled');
        });
    }

    // ===== 自动关闭消息提示 =====
    var alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000); // 5秒后自动关闭
    });

    // ===== 删除确认对话框增强 =====
    var deleteForms = document.querySelectorAll('form[onsubmit*="confirm"]');
    deleteForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            var confirmed = confirm('确定要执行此操作吗？此操作不可撤销。');
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });

    // ===== 搜索框回车提交 =====
    var searchInputs = document.querySelectorAll('input[name="search"]');
    searchInputs.forEach(function (input) {
        input.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                input.closest('form').submit();
            }
        });
    });

    // ===== 表格行点击高亮 =====
    var tableRows = document.querySelectorAll('table tbody tr');
    tableRows.forEach(function (row) {
        row.addEventListener('click', function (e) {
            // 如果点击的是按钮或链接，不处理
            if (e.target.closest('button') || e.target.closest('a') || e.target.closest('input') || e.target.closest('select')) {
                return;
            }
            // 移除其他行的高亮
            tableRows.forEach(function (r) {
                r.classList.remove('table-active');
            });
            row.classList.add('table-active');
        });
    });

});
