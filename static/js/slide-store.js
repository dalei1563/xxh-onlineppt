/**
 * SlideStore - 幻灯片与演示状态的统一前端存储。
 * 负责：从 API 加载幻灯片、WebSocket 实时同步、维护当前页/顺序/游戏状态。
 * 所有页面（slides/editor/controller）共享此模块。
 */
(function(global) {
    'use strict';

    function SlideStore() {
        this.slides = [];          // SlideInfo 数组
        this.slideOrder = [];      // slide_id 数组
        this.currentSlideId = '';
        this.total = 0;
        this.currentPosition = 1;
        this.isGameActive = false;
        this.currentRound = '';
        this.ws = new WsClient();

        // 事件回调
        this.onSlidesChange = null;
        this.onCurrentSlideChange = null;
        this.onGameStateChange = null;
        this.onConnectionStatusChange = null;
        this.onSlideCreated = null;
        this.onSlideUpdated = null;
        this.onSlideDeleted = null;
        this.onSlidesReordered = null;

        this._bindWsEvents();
    }

    SlideStore.prototype._bindWsEvents = function() {
        const self = this;

        this.ws.on('presentation_state', function(data) {
            self.currentSlideId = data.current_slide_id || '';
            self.slideOrder = data.slide_order || [];
            self.total = data.total || 0;
            self.currentPosition = data.current_position || 1;
            self.isGameActive = data.is_game_active || false;
            self.currentRound = data.current_round || '';
            self._notifyCurrentSlideChange();
            self._notifyGameStateChange();
        });

        this.ws.on('goto', function(data) {
            self.currentSlideId = data.slide;
            self.currentPosition = self.slideOrder.indexOf(data.slide) + 1;
            self._notifyCurrentSlideChange();
        });

        this.ws.on('slides_reordered', function(data) {
            self.slideOrder = data.order || [];
            self.total = self.slideOrder.length;
            self.currentPosition = self.slideOrder.indexOf(self.currentSlideId) + 1;
            // 关键修复：同步 slides 数组顺序，确保 slidesData 与 store 一致
            var reordered = [];
            data.order.forEach(function(id) {
                var slide = self.slides.find(function(s) { return s.slide_id === id; });
                if (slide) reordered.push(slide);
            });
            if (reordered.length === self.slides.length) {
                self.slides = reordered;
            }
            if (self.onSlidesReordered) self.onSlidesReordered(data.order);
            if (self.onSlidesChange) self.onSlidesChange(self.slides);
            self._notifyCurrentSlideChange();
        });

        this.ws.on('slide_created', function(data) {
            const slide = data.slide;
            if (!self._findById(slide.slide_id)) {
                self.slides.push(slide);
                self.slideOrder.push(slide.slide_id);
                self.total = self.slideOrder.length;
            }
            if (self.onSlideCreated) self.onSlideCreated(slide);
            if (self.onSlidesChange) self.onSlidesChange(self.slides);
        });

        this.ws.on('slide_updated', function(data) {
            const slide = data.slide;
            const idx = self.slides.findIndex(function(s) { return s.slide_id === slide.slide_id; });
            if (idx >= 0) {
                self.slides[idx] = slide;
            }
            if (self.onSlideUpdated) self.onSlideUpdated(slide);
            if (self.onSlidesChange) self.onSlidesChange(self.slides);
        });

        this.ws.on('slide_deleted', function(data) {
            const slideId = data.slide_id;
            self.slides = self.slides.filter(function(s) { return s.slide_id !== slideId; });
            self.slideOrder = self.slideOrder.filter(function(id) { return id !== slideId; });
            self.total = self.slideOrder.length;
            if (self.currentSlideId === slideId && self.slideOrder.length > 0) {
                self.currentSlideId = self.slideOrder[0];
                self.currentPosition = 1;
            }
            if (self.onSlideDeleted) self.onSlideDeleted(slideId);
            if (self.onSlidesChange) self.onSlidesChange(self.slides);
            self._notifyCurrentSlideChange();
        });

        this.ws.on('game_control', function(data) {
            if (data.action === 'started') {
                self.isGameActive = true;
                self.currentRound = data.round_name || '';
            } else if (data.action === 'ended' || data.action === 'reset') {
                self.isGameActive = false;
                self.currentRound = '';
            }
            self._notifyGameStateChange();
        });

        this.ws.onStatusChange = function(status) {
            if (self.onConnectionStatusChange) self.onConnectionStatusChange(status);
        };
    };

    SlideStore.prototype.init = function() {
        const self = this;
        return fetch('/api/slides')
            .then(function(res) { return res.json(); })
            .then(function(slides) {
                self.slides = slides || [];
                self.slideOrder = slides.map(function(s) { return s.slide_id; });
                self.total = self.slideOrder.length;
                if (self.total > 0 && !self.currentSlideId) {
                    self.currentSlideId = self.slideOrder[0];
                    self.currentPosition = 1;
                }
                if (self.onSlidesChange) self.onSlidesChange(self.slides);
                self.ws.connect();
            })
            .catch(function(err) {
                console.error('[SlideStore] Failed to load slides:', err);
                self.ws.connect();
            });
    };

    SlideStore.prototype._findById = function(slideId) {
        return this.slides.find(function(s) { return s.slide_id === slideId; });
    };

    SlideStore.prototype.getCurrentSlide = function() {
        return this._findById(this.currentSlideId);
    };

    SlideStore.prototype.getSlideById = function(slideId) {
        return this._findById(slideId);
    };

    SlideStore.prototype.getSlideByPosition = function(pos) {
        if (pos < 1 || pos > this.slideOrder.length) return null;
        return this._findById(this.slideOrder[pos - 1]);
    };

    SlideStore.prototype._notifyCurrentSlideChange = function() {
        if (this.onCurrentSlideChange) {
            this.onCurrentSlideChange(this.currentSlideId, this.currentPosition, this.total);
        }
    };

    SlideStore.prototype._notifyGameStateChange = function() {
        if (this.onGameStateChange) {
            this.onGameStateChange(this.isGameActive, this.currentRound);
        }
    };

    // ---- 导航控制 ----

    SlideStore.prototype.next = function() {
        this.ws.send({ type: 'next' });
    };

    SlideStore.prototype.prev = function() {
        this.ws.send({ type: 'prev' });
    };

    SlideStore.prototype.first = function() {
        this.ws.send({ type: 'first' });
    };

    SlideStore.prototype.last = function() {
        this.ws.send({ type: 'last' });
    };

    SlideStore.prototype.goto = function(slideId) {
        this.ws.send({ type: 'goto', slide: slideId });
    };

    SlideStore.prototype.gotoPosition = function(pos) {
        const slide = this.getSlideByPosition(pos);
        if (slide) this.goto(slide.slide_id);
    };

    SlideStore.prototype.sync = function() {
        this.ws.send({ type: 'sync', slide: this.currentSlideId });
    };

    SlideStore.prototype.toggleFullscreen = function() {
        this.ws.send({ type: 'fullscreen' });
    };

    SlideStore.prototype.replayVideo = function() {
        this.ws.send({ type: 'replay_video' });
    };

    // ---- 发送通用消息 ----

    SlideStore.prototype.send = function(msg) {
        this.ws.send(msg);
    };

    global.SlideStore = SlideStore;
})(window);
