/* ============================================
   造价智能助手 - 公共 JavaScript
   侧边栏交互、主题切换、通用工具函数
   ============================================ */

(function () {
  'use strict';

  // ========== 工具函数 ==========
  const Utils = {
    // 获取当前时间（HH:MM）
    getCurrentTime: function () {
      const now = new Date();
      return now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    },

    // 格式化数字（千分位）
    formatNumber: function (num, decimals) {
      if (decimals === undefined) decimals = 2;
      const parts = Number(num).toFixed(decimals).split('.');
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return parts.join('.');
    },

    // 防抖函数
    debounce: function (func, wait) {
      let timeout;
      return function () {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(function () {
          func.apply(context, args);
        }, wait);
      };
    },

    // 节流函数
    throttle: function (func, limit) {
      let inThrottle;
      return function () {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
          func.apply(context, args);
          inThrottle = true;
          setTimeout(function () {
            inThrottle = false;
          }, limit);
        }
      };
    },

    // 从 localStorage 读取
    getStorage: function (key, defaultValue) {
      try {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : defaultValue;
      } catch (e) {
        return defaultValue;
      }
    },

    // 写入 localStorage
    setStorage: function (key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch (e) {
        console.warn('localStorage 写入失败:', e);
      }
    },

    // 移动端检测
    isMobile: function () {
      return window.innerWidth <= 1024;
    }
  };

  // ========== 侧边栏管理 ==========
  const Sidebar = {
    element: null,
    overlay: null,
    mainContent: null,
    isCollapsed: false,
    isMobileOpen: false,

    init: function () {
      this.element = document.querySelector('.sidebar');
      this.overlay = document.querySelector('.sidebar-overlay');
      this.mainContent = document.querySelector('.main-content');

      if (!this.element) return;

      // 绑定折叠按钮事件
      const toggleBtns = document.querySelectorAll('.sidebar-toggle');
      toggleBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
          Sidebar.toggle();
        });
      });

      // 遮罩点击关闭（移动端）
      if (this.overlay) {
        this.overlay.addEventListener('click', function () {
          Sidebar.closeMobile();
        });
      }

      // 读取保存的状态
      const savedCollapsed = Utils.getStorage('sidebarCollapsed', false);
      if (savedCollapsed && !Utils.isMobile()) {
        this.collapse();
      }

      // 窗口大小变化响应
      window.addEventListener('resize', Utils.debounce(function () {
        Sidebar.handleResize();
      }, 150));

      // 导航项点击（移动端自动关闭）
      const navItems = this.element.querySelectorAll('.nav-item');
      navItems.forEach(function (item) {
        item.addEventListener('click', function () {
          if (Utils.isMobile()) {
            Sidebar.closeMobile();
          }
        });
      });
    },

    toggle: function () {
      if (Utils.isMobile()) {
        this.toggleMobile();
      } else {
        this.toggleCollapse();
      }
    },

    toggleCollapse: function () {
      if (this.isCollapsed) {
        this.expand();
      } else {
        this.collapse();
      }
    },

    collapse: function () {
      if (!this.element) return;
      this.element.classList.add('collapsed');
      if (this.mainContent) {
        this.mainContent.classList.add('sidebar-collapsed');
      }
      this.isCollapsed = true;
      Utils.setStorage('sidebarCollapsed', true);
    },

    expand: function () {
      if (!this.element) return;
      this.element.classList.remove('collapsed');
      if (this.mainContent) {
        this.mainContent.classList.remove('sidebar-collapsed');
      }
      this.isCollapsed = false;
      Utils.setStorage('sidebarCollapsed', false);
    },

    toggleMobile: function () {
      if (this.isMobileOpen) {
        this.closeMobile();
      } else {
        this.openMobile();
      }
    },

    openMobile: function () {
      if (!this.element) return;
      this.element.classList.add('mobile-open');
      if (this.overlay) {
        this.overlay.classList.add('show');
      }
      this.isMobileOpen = true;
      document.body.style.overflow = 'hidden';
    },

    closeMobile: function () {
      if (!this.element) return;
      this.element.classList.remove('mobile-open');
      if (this.overlay) {
        this.overlay.classList.remove('show');
      }
      this.isMobileOpen = false;
      document.body.style.overflow = '';
    },

    handleResize: function () {
      if (!Utils.isMobile()) {
        // 桌面端：关闭移动端状态
        this.closeMobile();
        // 恢复折叠状态
        const savedCollapsed = Utils.getStorage('sidebarCollapsed', false);
        if (savedCollapsed) {
          this.collapse();
        } else {
          this.expand();
        }
      } else {
        // 移动端：确保折叠状态清除
        if (this.element) {
          this.element.classList.remove('collapsed');
        }
        if (this.mainContent) {
          this.mainContent.classList.remove('sidebar-collapsed');
        }
      }
    }
  };

  // ========== 主题管理 ==========
  const Theme = {
    current: 'light',

    init: function () {
      // 读取保存的主题
      const savedTheme = Utils.getStorage('theme', 'light');
      this.setTheme(savedTheme);

      // 绑定主题切换按钮
      const themeBtns = document.querySelectorAll('[data-theme-toggle]');
      themeBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
          Theme.toggle();
        });
      });
    },

    setTheme: function (theme) {
      this.current = theme;
      document.documentElement.setAttribute('data-theme', theme);
      Utils.setStorage('theme', theme);

      // 更新主题切换按钮图标
      const themeBtns = document.querySelectorAll('[data-theme-toggle]');
      themeBtns.forEach(function (btn) {
        const icon = btn.querySelector('[data-icon]');
        if (icon) {
          // 重新创建图标以确保 lucide 更新
          icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon');
          if (window.lucide) {
            lucide.createIcons({ attrs: { 'stroke-width': 2 } });
          }
        }
      });
    },

    toggle: function () {
      this.setTheme(this.current === 'light' ? 'dark' : 'light');
    }
  };

  // ========== 导航激活状态 ==========
  const Navigation = {
    init: function () {
      // 根据当前页面设置激活状态
      const path = window.location.pathname;
      const pageName = path.substring(path.lastIndexOf('/') + 1) || 'chat.html';

      const navMap = {
        'chat.html': 'nav-chat',
        'index.html': 'nav-chat',
        'boq.html': 'nav-boq',
        'audit.html': 'nav-audit',
        'dashboard.html': 'nav-dashboard',
        'pipeline.html': 'nav-pipeline'
      };

      const activeId = navMap[pageName] || 'nav-chat';
      const activeNav = document.querySelector('[data-dom-id="' + activeId + '"]');
      if (activeNav) {
        activeNav.classList.add('active');
      }
    }
  };

  // ========== 初始化 ==========
  function init() {
    Sidebar.init();
    Theme.init();
    Navigation.init();

    // 初始化 Lucide 图标
    if (window.lucide) {
      lucide.createIcons({ attrs: { 'stroke-width': 2 } });
    }

    // 页面入场动画
    document.body.style.opacity = '0';
    requestAnimationFrame(function () {
      document.body.style.transition = 'opacity 0.3s ease';
      document.body.style.opacity = '1';
    });
  }

  // 暴露到全局
  window.CostApp = {
    Utils: Utils,
    Sidebar: Sidebar,
    Theme: Theme
  };

  // DOM 加载完成后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
