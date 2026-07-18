/**
 * WebSocket client - 统一 WebSocket 连接管理。
 * 提供：自动重连、消息分发、send/sendJson 方法。
 */
(function(global) {
    'use strict';

    function WsClient(url) {
        this.url = url || (function() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            return protocol + '//' + window.location.host + '/ws';
        })();
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 20;
        this.handlers = {};  // type -> array of callbacks
        this.status = 'disconnected';
        this.onStatusChange = null;
    }

    WsClient.prototype.connect = function() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }
        this.status = 'connecting';
        this._notifyStatus();

        this.ws = new WebSocket(this.url);
        const self = this;

        this.ws.onopen = function() {
            console.log('[WS] Connected');
            self.reconnectAttempts = 0;
            self.status = 'connected';
            self._notifyStatus();
        };

        this.ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                self._dispatch(data);
            } catch (e) {
                console.warn('[WS] Invalid JSON:', event.data);
            }
        };

        this.ws.onclose = function() {
            console.log('[WS] Disconnected');
            self.status = 'disconnected';
            self._notifyStatus();
            self._attemptReconnect();
        };

        this.ws.onerror = function(error) {
            console.error('[WS] Error:', error);
        };
    };

    WsClient.prototype._attemptReconnect = function() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(2000 * this.reconnectAttempts, 10000);
            console.log('[WS] Reconnecting in ' + delay + 'ms (attempt ' + this.reconnectAttempts + ')');
            setTimeout(this.connect.bind(this), delay);
        }
    };

    WsClient.prototype._notifyStatus = function() {
        if (typeof this.onStatusChange === 'function') {
            this.onStatusChange(this.status);
        }
    };

    WsClient.prototype._dispatch = function(data) {
        const type = data.type;
        if (!type) return;
        const callbacks = this.handlers[type] || [];
        callbacks.forEach(function(cb) {
            try {
                cb(data);
            } catch (e) {
                console.error('[WS] Handler error for ' + type + ':', e);
            }
        });
        // also dispatch to wildcard handlers
        const all = this.handlers['*'] || [];
        all.forEach(function(cb) {
            try {
                cb(data);
            } catch (e) {
                console.error('[WS] Wildcard handler error:', e);
            }
        });
    };

    WsClient.prototype.on = function(type, callback) {
        if (!this.handlers[type]) {
            this.handlers[type] = [];
        }
        this.handlers[type].push(callback);
        return this;
    };

    WsClient.prototype.off = function(type, callback) {
        const list = this.handlers[type];
        if (!list) return;
        const idx = list.indexOf(callback);
        if (idx >= 0) list.splice(idx, 1);
    };

    WsClient.prototype.send = function(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
            return true;
        }
        console.warn('[WS] Not connected, cannot send');
        return false;
    };

    WsClient.prototype.isConnected = function() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    };

    global.WsClient = WsClient;
})(window);
