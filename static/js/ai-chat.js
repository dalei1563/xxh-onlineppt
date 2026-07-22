/** Browser client for the server-relayed GLM-Realtime session. */
(function () {
    'use strict';

    var LISTEN_VIDEO = '/static/assets/聆听.mp4';
    var SPEAK_VIDEO = '/static/assets/口述.mp4';
    var INPUT_SAMPLE_RATE = 16000;
    var OUTPUT_SAMPLE_RATE = 24000;
    // Server-VAD keeps streaming the microphone between turns.  Put an upper
    // bound on one hands-free listening period so an unattended slide cannot
    // keep incurring audio charges indefinitely.
    var MAX_REALTIME_LISTEN_MS = 90000;

    var ws = null;
    var stream = null;
    var inputContext = null;
    var processor = null;
    var source = null;
    var outputContext = null;
    var activeSources = [];
    var nextPlayTime = 0;
    var isRecording = false;
    var realtimeReady = false;
    var turnMode = 'realtime';
    var startWhenReady = false;
    var reconnectTimer = null;
    var realtimeStopTimer = null;

    var avatarVideo, avatarRing, statusEl, statusWrap, stageHint;
    var realtimeBtn, manualBtn, realtimeActionLabel, realtimeActionHint, manualActionLabel, clearBtn;
    var turnEmpty, turnContent, userTurnText, assistantTurnText;

    function init() {
        avatarVideo = document.getElementById('aiAvatarVideo');
        avatarRing = document.getElementById('aiAvatarRing');
        statusEl = document.getElementById('aiChatStatus');
        statusWrap = statusEl ? statusEl.parentElement : null;
        stageHint = document.getElementById('aiStageHint');
        realtimeBtn = document.getElementById('aiRealtimeBtn');
        manualBtn = document.getElementById('aiManualBtn');
        realtimeActionLabel = document.querySelector('.realtime-action-label');
        realtimeActionHint = document.querySelector('.realtime-action-hint');
        manualActionLabel = document.querySelector('.manual-action-label');
        clearBtn = document.getElementById('aiClearBtn');
        turnEmpty = document.getElementById('aiTurnEmpty');
        turnContent = document.getElementById('aiTurnContent');
        userTurnText = document.getElementById('aiCurrentUserText');
        assistantTurnText = document.getElementById('aiCurrentAssistantText');
        if (!realtimeBtn || !manualBtn || !turnContent) return;

        realtimeBtn.addEventListener('click', function () { activateMode('realtime'); });
        manualBtn.addEventListener('click', function () { activateMode('manual'); });
        if (clearBtn) clearBtn.addEventListener('click', resetConversation);
        connectWebSocket();
    }

    function connectWebSocket() {
        clearTimeout(reconnectTimer);
        realtimeReady = false;
        setControlsEnabled(false);
        setConversationState('connecting', '正在连接实时对话', '正在建立安全连接');
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(protocol + '//' + window.location.host + '/ws');
        ws.onopen = function () { startSession(turnMode); };
        ws.onmessage = function (event) {
            try { handleMessage(JSON.parse(event.data)); }
            catch (error) { console.warn('[Realtime] Invalid message', error); }
        };
        ws.onclose = function () {
            stopRecording(false);
            realtimeReady = false;
            setControlsEnabled(false);
            setConversationState('error', '连接已断开', '正在尝试重新连接');
            reconnectTimer = setTimeout(connectWebSocket, 2000);
        };
        ws.onerror = function () { setConversationState('error', '实时连接异常', '请稍候，正在重试'); };
    }

    function startSession(mode) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        turnMode = mode === 'manual' ? 'manual' : 'realtime';
        realtimeReady = false;
        setControlsEnabled(false);
        setConversationState('connecting', '正在切换' + (turnMode === 'manual' ? '手动模式' : '实时模式'), '正在建立新的对话会话');
        renderModeControls();
        ws.send(JSON.stringify({ type: 'ai_realtime_start', audio: true, mode: turnMode }));
    }

    function activateMode(mode) {
        if (!realtimeReady && mode === turnMode) return;
        if (mode !== turnMode) {
            startWhenReady = true;
            stopRecording(false);
            startSession(mode);
            return;
        }
        if (isRecording) stopRecording(turnMode === 'manual');
        else startRecording();
    }

    function handleMessage(data) {
        switch (data.type) {
            case 'ai_realtime_status': handleStatus(data); break;
            case 'ai_realtime_user_transcript': setUserTurn(data.text); break;
            case 'ai_realtime_text_delta': appendAssistantText(data.delta); break;
            case 'ai_realtime_text_done': finishAssistantText(data.text); break;
            case 'ai_realtime_audio_delta':
                setConversationState('speaking', 'AI 正在回答', '可随时再次开始说话打断 AI');
                enqueuePcm(data.audio, data.sample_rate || OUTPUT_SAMPLE_RATE);
                break;
            case 'error':
                realtimeReady = false;
                setControlsEnabled(false);
                setConversationState('error', data.message || '实时服务异常', '请重新开始对话');
                break;
        }
    }

    function handleStatus(data) {
        var state = data.status || 'idle';
        var message = data.message || '';
        if (state === 'ready') {
            realtimeReady = true;
            setControlsEnabled(true);
            if (turnMode === 'realtime' && isRecording) {
                showRealtimeListeningState();
            } else {
                setConversationState('idle', turnMode === 'manual' ? '手动模式已就绪' : '实时模式已就绪', message || modeHint());
            }
            if (startWhenReady) {
                startWhenReady = false;
                startRecording();
            }
        } else if (state === 'listening') {
            setConversationState('listening', '正在聆听', message || '说完后会自动回复');
            stopPlayback();
            switchVideo(LISTEN_VIDEO);
        } else if (state === 'thinking') {
            setConversationState('thinking', '正在理解你的问题', message || 'AI 正在组织回答');
            switchVideo(SPEAK_VIDEO);
        } else if (state === 'connecting') {
            realtimeReady = false;
            setControlsEnabled(false);
            setConversationState('connecting', '正在连接实时对话', message || '正在建立安全连接');
        } else if (state === 'error') {
            realtimeReady = false;
            stopRecording(false);
            stopPlayback();
            setControlsEnabled(false);
            setConversationState('error', '实时对话不可用', message || '请重新开始对话');
        }
    }

    function modeHint() {
        return turnMode === 'manual' ? '点击录音，说完后再次点击停止并发送' : '点击实时对话开始聆听；再次点击可停止';
    }

    function showRealtimeListeningState() {
        setConversationState('listening', '正在实时聆听', '可直接继续说话；点击“实时对话”停止（单次最长 90 秒）');
        switchVideo(LISTEN_VIDEO);
    }

    function setConversationState(state, title, hint) {
        if (statusWrap) statusWrap.dataset.state = state;
        if (statusEl) statusEl.textContent = title;
        if (stageHint) stageHint.textContent = hint;
        setAvatarState(state === 'idle' || state === 'connecting' || state === 'error' ? '' : state);
    }

    function setControlsEnabled(enabled) {
        realtimeBtn.disabled = !enabled;
        manualBtn.disabled = !enabled;
        renderModeControls();
    }

    function renderModeControls() {
        realtimeBtn.classList.toggle('is-selected', turnMode === 'realtime');
        manualBtn.classList.toggle('is-selected', turnMode === 'manual');
        realtimeBtn.classList.toggle('is-recording', turnMode === 'realtime' && isRecording);
        manualBtn.classList.toggle('is-recording', turnMode === 'manual' && isRecording);
        if (realtimeActionLabel) realtimeActionLabel.textContent = turnMode === 'realtime' && isRecording ? '点击停止' : '实时对话';
        if (realtimeActionHint) realtimeActionHint.textContent = turnMode === 'realtime' && isRecording ? '正在实时聆听' : '自动断句，连续交流';
        if (manualActionLabel) manualActionLabel.textContent = turnMode === 'manual' && isRecording ? '点击停止' : '点击录音';
    }

    async function startRecording() {
        if (!ws || ws.readyState !== WebSocket.OPEN || !realtimeReady || isRecording) return;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
            });
            inputContext = new (window.AudioContext || window.webkitAudioContext)();
            outputContext = outputContext || new (window.AudioContext || window.webkitAudioContext)({ sampleRate: OUTPUT_SAMPLE_RATE });
            await inputContext.resume();
            await outputContext.resume();
            source = inputContext.createMediaStreamSource(stream);
            processor = inputContext.createScriptProcessor(4096, 1, 1);
            processor.onaudioprocess = function (event) {
                if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
                var pcm = floatToPcm16(downsample(event.inputBuffer.getChannelData(0), inputContext.sampleRate, INPUT_SAMPLE_RATE));
                ws.send(JSON.stringify({ type: 'ai_realtime_audio_append', audio: bytesToBase64(pcm) }));
            };
            source.connect(processor);
            var silentGain = inputContext.createGain();
            silentGain.gain.value = 0;
            processor.connect(silentGain);
            silentGain.connect(inputContext.destination);
            isRecording = true;
            if (turnMode === 'realtime') {
                clearTimeout(realtimeStopTimer);
                realtimeStopTimer = setTimeout(function () {
                    if (isRecording && turnMode === 'realtime') {
                        stopRecording(false);
                        setConversationState('idle', '实时聆听已自动停止', '为避免持续计费已停止麦克风；点击实时对话可再次开始');
                    }
                }, MAX_REALTIME_LISTEN_MS);
            }
            showCurrentTurn('正在识别语音…');
            if (turnMode === 'realtime') showRealtimeListeningState();
            else setConversationState('listening', '正在聆听', '再次点击“点击停止”后发送本段录音');
            renderModeControls();
            switchVideo(LISTEN_VIDEO);
        } catch (error) {
            console.error('[Realtime] Microphone error', error);
            setConversationState('error', '无法访问麦克风', '请确认正在使用 HTTPS 且已授予麦克风权限');
            stopRecording(false);
        }
    }

    function stopRecording(commitManualTurn) {
        var wasRecording = isRecording;
        clearTimeout(realtimeStopTimer);
        realtimeStopTimer = null;
        if (processor) { processor.disconnect(); processor.onaudioprocess = null; processor = null; }
        if (source) { source.disconnect(); source = null; }
        if (stream) { stream.getTracks().forEach(function (track) { track.stop(); }); stream = null; }
        if (inputContext) { inputContext.close(); inputContext = null; }
        isRecording = false;
        renderModeControls();
        if (wasRecording && commitManualTurn && ws && ws.readyState === WebSocket.OPEN) {
            if (userTurnText && userTurnText.textContent === '正在识别语音…') userTurnText.textContent = '本段录音已发送';
            setConversationState('thinking', '正在理解你的问题', 'AI 正在生成回答');
            ws.send(JSON.stringify({ type: 'ai_realtime_audio_commit' }));
        } else if (wasRecording && turnMode === 'realtime' && realtimeReady) {
            setConversationState('idle', '实时模式已就绪', '点击实时对话开始聆听');
            switchVideo(LISTEN_VIDEO);
        }
    }

    function showCurrentTurn(userText) {
        if (turnEmpty) turnEmpty.hidden = true;
        turnContent.hidden = false;
        if (userText !== undefined) userTurnText.textContent = userText || '正在识别语音…';
        assistantTurnText.textContent = '等待 AI 回答…';
    }

    function setUserTurn(text) {
        if (!text) return;
        showCurrentTurn(text);
    }

    function appendAssistantText(delta) {
        if (!delta) return;
        if (turnContent.hidden) showCurrentTurn('本轮语音输入');
        if (assistantTurnText.textContent === '等待 AI 回答…') assistantTurnText.textContent = '';
        assistantTurnText.textContent += delta;
    }

    function finishAssistantText(text) {
        if (!text) return;
        if (turnContent.hidden) showCurrentTurn('本轮语音输入');
        assistantTurnText.textContent = text;
    }

    function resetConversation() {
        stopPlayback();
        stopRecording(false);
        if (turnEmpty) turnEmpty.hidden = false;
        turnContent.hidden = true;
        userTurnText.textContent = '正在识别语音…';
        assistantTurnText.textContent = '等待 AI 回答…';
        if (ws && ws.readyState === WebSocket.OPEN) startSession(turnMode);
    }

    function downsample(input, fromRate, toRate) {
        if (fromRate === toRate) return input;
        var ratio = fromRate / toRate;
        var output = new Float32Array(Math.round(input.length / ratio));
        for (var i = 0; i < output.length; i++) {
            var start = Math.floor(i * ratio), end = Math.min(input.length, Math.floor((i + 1) * ratio)), sum = 0;
            for (var j = start; j < end; j++) sum += input[j];
            output[i] = sum / Math.max(1, end - start);
        }
        return output;
    }

    function floatToPcm16(samples) {
        var bytes = new Uint8Array(samples.length * 2), view = new DataView(bytes.buffer);
        for (var i = 0; i < samples.length; i++) {
            var sample = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
        }
        return bytes;
    }

    function bytesToBase64(bytes) { var binary = ''; for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]); return btoa(binary); }
    function base64ToBytes(value) { var binary = atob(value || ''), bytes = new Uint8Array(binary.length); for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i); return bytes; }
    function getOutputContext() { outputContext = outputContext || new (window.AudioContext || window.webkitAudioContext)({ sampleRate: OUTPUT_SAMPLE_RATE }); return outputContext; }

    function enqueuePcm(base64, sampleRate) {
        if (!base64) return;
        var context = getOutputContext();
        context.resume().catch(function () {});
        var bytes = base64ToBytes(base64), view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), frames = Math.floor(bytes.byteLength / 2);
        var buffer = context.createBuffer(1, frames, sampleRate), output = buffer.getChannelData(0);
        for (var i = 0; i < frames; i++) output[i] = view.getInt16(i * 2, true) / 0x8000;
        var sourceNode = context.createBufferSource();
        sourceNode.buffer = buffer; sourceNode.connect(context.destination);
        var startAt = Math.max(context.currentTime + 0.05, nextPlayTime);
        sourceNode.start(startAt); nextPlayTime = startAt + buffer.duration; activeSources.push(sourceNode);
        sourceNode.onended = function () {
            activeSources = activeSources.filter(function (item) { return item !== sourceNode; });
            if (!activeSources.length && context.currentTime >= nextPlayTime - 0.02 && realtimeReady) {
                if (turnMode === 'realtime' && isRecording) showRealtimeListeningState();
                else {
                    setConversationState('idle', turnMode === 'manual' ? '手动模式已就绪' : '实时模式已就绪', modeHint());
                    switchVideo(LISTEN_VIDEO);
                }
            }
        };
        switchVideo(SPEAK_VIDEO);
    }

    function stopPlayback() { activeSources.forEach(function (item) { try { item.stop(); } catch (_) {} }); activeSources = []; nextPlayTime = 0; }
    function setAvatarState(state) {
        if (!avatarRing) return;
        var avatarState = state === 'listening' ? 'recording' : state;
        avatarRing.className = 'ai-avatar-wrapper' + (avatarState ? ' ' + avatarState : '');
    }
    function switchVideo(src) { if (!avatarVideo || avatarVideo.getAttribute('src') === src) return; avatarVideo.src = src; avatarVideo.load(); avatarVideo.play().catch(function () {}); }

    window.AIChat = {
        sendMessage: function (text) {
            if (!text || !ws || ws.readyState !== WebSocket.OPEN || !realtimeReady) return false;
            showCurrentTurn(text);
            ws.send(JSON.stringify({ type: 'ai_realtime_text', text: text }));
            return true;
        }
    };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
