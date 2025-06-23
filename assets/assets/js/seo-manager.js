// SEO Manager - Giải pháp hoàn hảo cho HTML/CSS/JS thuần
(function() {
    'use strict';
    
    // Cấu hình rules cho website
    const SEO_CONFIG = {
        // Domain chính
        domain: 'https://yourdomain.com',
        
        // Rules để xử lý canonical
        canonicalRules: {
            // Loại bỏ các parameters không cần thiết
            removeParams: ['utm_source', 'utm_medium', 'utm_campaign', 'fbclid', 'gclid', 'ref', 'source'],
            
            // Loại bỏ trailing slash
            removeTrailingSlash: true,
            
            // Force HTTPS
            forceHttps: true,
            
            // Loại bỏ www (hoặc force www nếu muốn)
            removeWww: true, // set false nếu muốn giữ www
            
            // Loại bỏ index.html, index.php
            removeIndexFiles: ['index.html', 'index.php', 'index.htm']
        },
        
        // Rules cho robots meta
        robotsRules: {
            // Trang không nên index
            noindexPatterns: [
                '/admin/', '/login/', '/register/', '/search', '/404', 
                '/thank-you', '/cart', '/checkout', '/private/'
            ],
            
            // Parameters khiến trang không nên index
            noindexParams: ['search', 'filter', 'sort', 'page'],
            
            // Default robots
            defaultRobots: 'index,follow'
        }
    };
    
    // Hàm tạo canonical URL chuẩn
    function generateCanonicalUrl() {
        let url = window.location.href;
        const config = SEO_CONFIG.canonicalRules;
        
        // 1. Force HTTPS
        if (config.forceHttps) {
            url = url.replace(/^http:/, 'https:');
        }
        
        // 2. Xử lý www
        if (config.removeWww) {
            url = url.replace(/^https?:\/\/www\./, 'https://');
        }
        
        // 3. Parse URL
        const urlObj = new URL(url);
        
        // 4. Loại bỏ parameters không cần thiết
        if (config.removeParams && config.removeParams.length > 0) {
            config.removeParams.forEach(param => {
                urlObj.searchParams.delete(param);
            });
        }
        
        // 5. Loại bỏ trailing slash
        if (config.removeTrailingSlash && urlObj.pathname.endsWith('/') && urlObj.pathname.length > 1) {
            urlObj.pathname = urlObj.pathname.slice(0, -1);
        }
        
        // 6. Loại bỏ index files
        if (config.removeIndexFiles) {
            config.removeIndexFiles.forEach(indexFile => {
                if (urlObj.pathname.endsWith('/' + indexFile)) {
                    urlObj.pathname = urlObj.pathname.replace('/' + indexFile, '/');
                    if (urlObj.pathname === '//' ) urlObj.pathname = '/';
                }
            });
        }
        
        return urlObj.toString();
    }
    
    // Hàm xác định robots meta
    function getRobotsMeta() {
        const config = SEO_CONFIG.robotsRules;
        const currentPath = window.location.pathname;
        const searchParams = window.location.search;
        
        // Kiểm tra noindex patterns
        for (let pattern of config.noindexPatterns) {
            if (currentPath.includes(pattern)) {
                return 'noindex,follow';
            }
        }
        
        // Kiểm tra noindex parameters
        if (searchParams) {
            const urlParams = new URLSearchParams(searchParams);
            for (let param of config.noindexParams) {
                if (urlParams.has(param)) {
                    return 'noindex,follow';
                }
            }
        }
        
        return config.defaultRobots;
    }
    
    // Hàm chính xử lý SEO
    function processSEO() {
        // 1. Xóa tất cả canonical và robots cũ
        const oldCanonicals = document.querySelectorAll('link[rel="canonical"]');
        const oldRobots = document.querySelectorAll('meta[name="robots"], meta[name="googlebot"]');
        
        oldCanonicals.forEach(el => el.remove());
        oldRobots.forEach(el => el.remove());
        
        // 2. Tạo canonical mới
        const canonicalUrl = generateCanonicalUrl();
        const canonicalTag = document.createElement('link');
        canonicalTag.rel = 'canonical';
        canonicalTag.href = canonicalUrl;
        document.head.appendChild(canonicalTag);
        
        // 3. Tạo robots meta mới
        const robotsContent = getRobotsMeta();
        const robotsTag = document.createElement('meta');
        robotsTag.name = 'robots';
        robotsTag.content = robotsContent;
        document.head.appendChild(robotsTag);
        
        // 4. Clean URL trong browser (không làm trang reload)
        if (window.history.replaceState) {
            const cleanUrl = canonicalUrl;
            if (cleanUrl !== window.location.href) {
                window.history.replaceState(null, document.title, cleanUrl);
            }
        }
        
        // 5. Log để debug (có thể xóa trong production)
        console.log('SEO Manager:', {
            canonical: canonicalUrl,
            robots: robotsContent,
            originalUrl: window.location.href
        });
    }
    
    // Chạy ngay khi DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', processSEO);
    } else {
        processSEO();
    }
    
    // Export để có thể gọi manually nếu cần
    window.SEOManager = {
        process: processSEO,
        config: SEO_CONFIG,
        generateCanonical: generateCanonicalUrl,
        getRobots: getRobotsMeta
    };
    
})();