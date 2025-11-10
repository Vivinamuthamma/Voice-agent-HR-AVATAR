class InterviewApp {
    constructor() {
        this.currentStep = 'setup';
        this.sessionData = null;
        this.livekitRoom = null;
        this.isConnected = false;
        this.audioLevelInterval = null;
        this.interviewProgress = 0;
        this.connectionRetries = 0;
        this.maxRetries = 3;
        this.retryDelay = 2000; // 2 seconds
        this.candidateName = null; // Store candidate name for identity checks
        this.statusPollingInterval = null; // For polling session status
        this.statusPollingAttempts = 0;
        this.maxStatusPollingAttempts = 30; // Poll for up to 30 seconds

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkSystemStatus();
        this.validateForm();
        this.setupErrorHandling();
    }

    setupErrorHandling() {
        // Global error handler for unhandled promises
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.showMessage('voiceMessage', 'danger',
                'An unexpected error occurred. Please refresh the page if issues persist.');
            event.preventDefault();
        });

        // Global error handler
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
        });
    }

    setupEventListeners() {
        // Form validation with debouncing
        const debounce = (func, wait) => {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        };

        const debouncedValidate = debounce(() => this.validateForm(), 300);

        // Form validation
        document.getElementById('candidateName').addEventListener('input', debouncedValidate);
        document.getElementById('position').addEventListener('input', debouncedValidate);
        document.getElementById('email').addEventListener('input', debouncedValidate);
        document.getElementById('jdFile').addEventListener('change', debouncedValidate);
        document.getElementById('resumeFile').addEventListener('change', debouncedValidate);

        // File size validation
        document.getElementById('jdFile').addEventListener('change', (e) => this.validateFileSize(e.target));
        document.getElementById('resumeFile').addEventListener('change', (e) => this.validateFileSize(e.target));

        // Start setup button
        document.getElementById('startSetupBtn').addEventListener('click', () => this.startInterviewSetup());
    }

    validateFileSize(fileInput) {
        const maxSize = 10 * 1024 * 1024; // 10MB
        const files = fileInput.files;

        if (files.length > 0) {
            const file = files[0];
            if (file.size > maxSize) {
                this.showMessage('setupMessage', 'danger',
                    `File "${file.name}" is too large. Maximum size is 10MB.`);
                fileInput.value = ''; // Clear the input
                return false;
            }
        }
        return true;
    }

    validateForm() {
        const name = document.getElementById('candidateName').value.trim();
        const position = document.getElementById('position').value.trim();
        const email = document.getElementById('email').value.trim();
        const jdFile = document.getElementById('jdFile').files[0];
        const resumeFile = document.getElementById('resumeFile').files[0];

        // Email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const isEmailValid = emailRegex.test(email);

        const isValid = name && position && email && isEmailValid && jdFile && resumeFile;
        const submitBtn = document.getElementById('startSetupBtn');

        submitBtn.disabled = !isValid;

        // Update submit button text based on validation
        if (isValid) {
            submitBtn.textContent = '🚀 Start Interview Setup';
            submitBtn.classList.remove('btn-secondary');
            submitBtn.classList.add('btn-primary');
        } else {
            submitBtn.textContent = 'Please complete all fields';
            submitBtn.classList.remove('btn-primary');
            submitBtn.classList.add('btn-secondary');
        }
        
        return isValid;
    }
    
async checkSystemStatus() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            const response = await fetch('/api/health', {
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            const data = await response.json();
            
            const statusEl = document.getElementById('systemStatus');
            
            if (response.ok && data.status === 'healthy') {
                statusEl.className = 'alert alert-success';
                statusEl.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="fas fa-check-circle me-2"></i>
                        <div>
                            <strong>System Ready</strong><br>
                            <small>All services configured</small>
                        </div>
                    </div>
                `;
                
                // Check LiveKit client library
                if (typeof LivekitClient !== 'undefined') {
                    console.log('✅ LiveKit client library loaded successfully');
                } else {
                    this.showMessage('setupMessage', 'warning', 
                        'LiveKit client library not available. Please refresh the page.');
                }
            } else {
                statusEl.className = 'alert alert-warning';
                statusEl.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <div>
                            <strong>System Partially Ready</strong><br>
                            <small>Some services may have limited functionality</small>
                        </div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('System status check failed:', error);
            const statusEl = document.getElementById('systemStatus');
            statusEl.className = 'alert alert-danger';
            
            if (error.name === 'AbortError') {
                statusEl.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="fas fa-times-circle me-2"></i>
                        <div>
                            <strong>Connection Timeout</strong><br>
                            <small>Backend server may be starting up. Please wait and refresh.</small>
                        </div>
                    </div>
                `;
            } else {
                statusEl.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="fas fa-times-circle me-2"></i>
                        <div>
                            <strong>System Check Failed</strong><br>
                            <small>Please verify backend connection and refresh the page</small>
                        </div>
                    </div>
                `;
            }
        }
    }
    
    async startInterviewSetup() {
        if (!this.validateForm()) {
            this.showMessage('setupMessage', 'danger', 'Please fill in all required fields correctly.');
            return;
        }
        
        // Disable the button to prevent double submission
        const submitBtn = document.getElementById('startSetupBtn');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Processing...';
        
        try {
            // Show processing section
            this.showSection('processing');
            this.updateProgress(10, 'Uploading files...', 'Preparing documents for analysis');
            
            // Upload files
            const uploadResult = await this.uploadFiles();
            if (!uploadResult.success) {
                throw new Error(uploadResult.error || 'File upload failed');
            }
            
            this.updateProgress(30, 'Analyzing documents...', 'AI is analyzing job requirements and candidate profile');
            
            // Analyze documents
            const analysisResult = await this.analyzeDocuments(uploadResult);
            if (!analysisResult.success) {
                throw new Error(analysisResult.error || 'Document analysis failed');
            }
            
            this.updateProgress(60, 'Generating questions...', 'Creating personalized interview questions');
            
            // Generate questions
            const questionsResult = await this.generateQuestions(uploadResult);
            if (!questionsResult.success) {
                throw new Error(questionsResult.error || 'Question generation failed');
            }
            
            this.updateProgress(80, 'Creating interview session...', 'Setting up voice interview room');
            
            // Create session
            const sessionResult = await this.createSession(uploadResult, analysisResult, questionsResult);
            if (!sessionResult.success) {
                throw new Error(sessionResult.error || 'Session creation failed');
            }

            this.updateProgress(100, 'Setup complete!', 'Ready to start voice interview');

            // Store session data
            this.sessionData = sessionResult.data;
            
            // Show voice section
            this.showSection('voice');
            this.updateInterviewProgress(0, questionsResult.questions.length);
            
            // Auto-connect after a brief pause
            setTimeout(() => {
                this.connectToInterview();
            }, 1000);
            
        } catch (error) {
            console.error('Setup failed:', error);
            this.showMessage('setupMessage', 'danger', `Setup failed: ${error.message}`);
            this.showSection('setup');
        } finally {
            // Re-enable button
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }
    
    async uploadFiles() {
        const formData = new FormData();
        formData.append('jd_file', document.getElementById('jdFile').files[0]);
        formData.append('resume_file', document.getElementById('resumeFile').files[0]);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('File upload timed out. Please try again with smaller files.');
            }
            throw error;
        }
    }
    
    async analyzeDocuments(uploadResult) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000); // 45 second timeout
        
        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jd_text: uploadResult.jd_full,
                    resume_text: uploadResult.resume_full
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Analysis failed with status ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('Document analysis timed out. Please try again.');
            }
            throw error;
        }
    }
    
    async generateQuestions(uploadResult) {
        const numQuestions = 6; // Default number of questions

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000);

        try {
            const response = await fetch('/api/generate-questions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jd_text: uploadResult.jd_full,
                    resume_text: uploadResult.resume_full,
                    num_questions: numQuestions
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Question generation failed with status ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('Question generation timed out. Please try again.');
            }
            throw error;
        }
    }
    
    async createSession(uploadResult, analysisResult, questionsResult) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        
        try {
            const response = await fetch('/api/create-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    candidate_name: document.getElementById('candidateName').value,
                    position: document.getElementById('position').value,
                    email: document.getElementById('email').value,
                    questions: questionsResult.questions,
                    analysis: analysisResult.analysis,
                    jd_full: uploadResult.jd_full,
                    resume_full: uploadResult.resume_full
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Session creation failed with status ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('Session creation timed out. Please try again.');
            }
            throw error;
        }
    }
    
    async connectToInterview() {
        if (!this.sessionData) {
            this.showMessage('voiceMessage', 'danger', 'No session data available. Please restart the setup process.');
            return;
        }

        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        
        try {
            connectBtn.disabled = true;
            this.updateConnectionStatus('connecting', 'Connecting to interview room...');

            // Check microphone permissions
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
                // Test successful, close the test stream
                stream.getTracks().forEach(track => track.stop());
                console.log('✅ Microphone access granted');
            } catch (permissionError) {
                if (permissionError.name === 'NotAllowedError' || permissionError.name === 'PermissionDeniedError') {
                    throw new Error('Microphone access denied. Please enable microphone permissions and refresh the page.');
                } else if (permissionError.name === 'NotFoundError') {
                    throw new Error('No microphone found. Please connect a microphone and try again.');
                } else {
                    throw new Error(`Microphone error: ${permissionError.message}`);
                }
            }

            // Check LiveKit availability
            if (typeof LivekitClient === 'undefined') {
                throw new Error('LiveKit client library not available. Please refresh the page.');
            }

            // Create room with enhanced configuration
            this.livekitRoom = new LivekitClient.Room({
                // Audio settings
                audioCaptureDefaults: {
                    autoGainControl: true,
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 24000,
                    channelCount: 1,
                },
                
                // Connection settings
                adaptiveStream: true,
                dynacast: true,
                
                // Experimental features
                expWebAudioMix: false, // Disable if causing issues
                
                // E2EE (if needed)
                e2eeEnabled: false,
            });

            // Enhanced event handlers
            this.setupLiveKitEvents();

            // Connect with timeout
            console.log('🔌 Connecting to LiveKit room...');
            console.log('Session data:', this.sessionData);
            console.log('LiveKit URL:', this.sessionData.livekit_url);
            console.log('Token available:', !!this.sessionData.candidate_token);

            // Validate session data
            if (!this.sessionData.livekit_url) {
                throw new Error('LiveKit URL is missing from session data');
            }
            if (!this.sessionData.candidate_token) {
                throw new Error('Candidate token is missing from session data');
            }

            // Validate URL format
            try {
                new URL(this.sessionData.livekit_url);
            } catch (urlError) {
                throw new Error(`Invalid LiveKit URL format: ${this.sessionData.livekit_url} - ${urlError.message}`);
            }

            const connectPromise = this.livekitRoom.connect(
                this.sessionData.livekit_url,
                this.sessionData.candidate_token
            );

            // Add connection timeout
            const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Connection timeout')), 30000)
            );

            await Promise.race([connectPromise, timeoutPromise]);
            console.log('✅ Connected to LiveKit room');

                // Enable microphone with improved error handling (voice-only interview)
                try {
                    console.log('🎤 Enabling microphone (voice-only interview)...');

                    // Set a timeout for microphone setup - only audio, no camera
                    const micSetupPromise = this.livekitRoom.localParticipant.setMicrophoneEnabled(true);
                    const micTimeoutPromise = new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('Microphone setup timeout')), 15000) // 15 second timeout
                    );

                    await Promise.race([micSetupPromise, micTimeoutPromise]);
                    console.log('✅ Microphone enabled (voice-only interview)');

                // Verify microphone is actually working - simplified and more robust
                await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
                const localParticipant = this.livekitRoom.localParticipant;

                // Simple verification - check for any audio tracks
                let hasAudioTracks = false;

                if (localParticipant.audioTracks && localParticipant.audioTracks.size > 0) {
                    console.log('✅ Microphone tracks verified (direct check)');
                    hasAudioTracks = true;
                } else {
                    // Check publications as fallback
                    const audioPublications = Array.from(localParticipant.trackPublications.values())
                        .filter(pub => pub.track && pub.track.kind === 'audio');

                    if (audioPublications.length > 0) {
                        console.log('✅ Microphone tracks verified (publications check)');
                        console.log(`📊 Audio track publications found: ${audioPublications.length}`);
                        hasAudioTracks = true;

                        // Log publication details for debugging
                        audioPublications.forEach((pub, index) => {
                            console.log(`  Publication ${index + 1}: ${pub.track.name || 'unnamed'} (${pub.source})`);
                        });
                    }
                }

                if (hasAudioTracks) {
                    console.log('✅ Microphone verification successful - agent should be able to hear you');
                } else {
                    console.warn('⚠️ No microphone tracks found after setup');
                    console.warn('🔧 This may cause the agent to say "I did not hear any answers"');
                    // Don't show warning to user - let the interview proceed
                }

                // Notify backend of successful connection
                this.notifyBackendOfConnection();

            } catch (micError) {
                console.error('Microphone enabling failed:', micError);

                // Provide more specific error messages
                let errorMessage = 'Microphone setup failed';
                if (micError.message.includes('timeout')) {
                    errorMessage = 'Microphone setup timed out. Please check your microphone permissions and try again.';
                } else if (micError.message.includes('Permission')) {
                    errorMessage = 'Microphone permission denied. Please allow microphone access and refresh the page.';
                } else if (micError.message.includes('NotFound')) {
                    errorMessage = 'No microphone found. Please connect a microphone and try again.';
                } else {
                    errorMessage = `Microphone setup failed: ${micError.message}`;
                }

                throw new Error(errorMessage);
            }

            this.isConnected = true;
            this.connectionRetries = 0; // Reset retry counter on success
            this.updateConnectionStatus('connected', 'Connected to interview - AI interviewer has joined');
            this.showInterviewProgress();
            this.startAudioLevelMonitoring();

            connectBtn.classList.add('d-none');
            disconnectBtn.classList.remove('d-none');

            // Clear any existing error messages
            this.clearMessage('voiceMessage');

        } catch (error) {
            console.error('Connection failed:', error);
            this.handleConnectionError(error);
        } finally {
            connectBtn.disabled = false;
        }
    }

    handleConnectionError(error) {
        const connectBtn = document.getElementById('connectBtn');
        
        // Determine if this is a retryable error
        const retryableErrors = [
            'Connection timeout',
            'Network error',
            'WebSocket connection failed',
            'Failed to connect'
        ];
        
        const isRetryable = retryableErrors.some(retryableError => 
            error.message.toLowerCase().includes(retryableError.toLowerCase())
        );

        if (isRetryable && this.connectionRetries < this.maxRetries) {
            this.connectionRetries++;
            this.updateConnectionStatus('connecting', 
                `Connection failed, retrying... (${this.connectionRetries}/${this.maxRetries})`);9
            
            setTimeout(() => {
                console.log(`Retry attempt ${this.connectionRetries}/${this.maxRetries}`);
                this.connectToInterview();
            }, this.retryDelay * this.connectionRetries);
            
        } else {
            // Final failure or non-retryable error
            this.connectionRetries = 0;
            this.updateConnectionStatus('disconnected', `Connection failed: ${error.message}`);
            
            let errorMessage = `Failed to connect: ${error.message}`;
            
            // Provide specific guidance for common issues
            if (error.message.includes('Microphone')) {
                errorMessage += '\n\n🎤 Microphone Issues:\n• Check if microphone is connected\n• Allow microphone permissions in browser\n• Try refreshing the page';
            } else if (error.message.includes('timeout')) {
                errorMessage += '\n\n⏱️ Connection Timeout:\n• Check your internet connection\n• Try refreshing the page\n• Contact support if issue persists';
            }
            
            this.showMessage('voiceMessage', 'danger', errorMessage);
            connectBtn.disabled = false;
        }
        
        // Clean up room if it was created
        if (this.livekitRoom) {
            try {
                this.livekitRoom.disconnect();
            } catch (e) {
                console.warn('Error disconnecting room during error handling:', e);
            }
            this.livekitRoom = null;
        }
    }
    
    setupLiveKitEvents() {
        if (!this.livekitRoom) return;
        
        console.log('📡 Setting up LiveKit event handlers');
        
        this.livekitRoom.on('participantConnected', (participant) => {
            console.log('👤 Participant connected:', participant.identity);
            if (participant.identity !== this.candidateName && participant.identity !== 'unknown') {
                this.showMessage('voiceMessage', 'success',
                    '🤖 AI interviewer has joined! The interview will begin shortly.');
                this.updateConnectionStatus('connected', 'AI interviewer connected - Interview starting');
            }
        });
        
        this.livekitRoom.on('participantDisconnected', (participant) => {
            console.log('👤 Participant disconnected:', participant.identity);
            if (participant.identity !== this.candidateName && participant.identity !== 'unknown') {
                // Agent disconnected - start polling for session status update
                console.log('🤖 AI interviewer disconnected, polling for status update...');
                this.showMessage('voiceMessage', 'info', 'AI interviewer has finished. Checking interview status...');
                this.updateConnectionStatus('disconnected', 'Checking interview status...');
                this.pollSessionStatus();
            }
        });
        
        this.livekitRoom.on('trackSubscribed', (track, publication, participant) => {
            console.log('🎵 Track subscribed:', track.kind, 'from', participant.identity);

            if (track.kind === 'video' && participant.identity !== this.candidateName && participant.identity !== 'unknown') {
                console.log('🎥 Subscribing to AI interviewer video (avatar)');
                this.handleAvatarVideoTrack(track, participant);
            }

            if (track.kind === 'audio' && participant.identity !== this.candidateName && participant.identity !== 'unknown') {
                console.log('🎵 Subscribing to AI interviewer audio');
                const audioElement = track.attach();
                audioElement.autoplay = true;
                audioElement.controls = false;
                audioElement.style.display = 'none'; // Hide the audio element
                document.body.appendChild(audioElement);

                // Set volume and play
                audioElement.volume = 0.8;
                audioElement.play().catch(e => {
                    console.warn("Could not auto-play AI audio:", e);
                    // Show user prompt to enable audio
                    this.showMessage('voiceMessage', 'info',
                        'Click here to enable AI interviewer audio', true, () => {
                            audioElement.play();
                        });
                });
            }
        });
        
        this.livekitRoom.on('trackUnsubscribed', (track, publication, participant) => {
            console.log('🎵 Track unsubscribed:', track.kind, 'from', participant.identity);

            if (track.kind === 'video' && participant.identity !== this.candidateName && participant.identity !== 'unknown') {
                console.log('🎥 Unsubscribing from AI interviewer video (avatar)');
                // Hide the avatar video
                const videoElement = document.getElementById('avatar-video');
                if (videoElement) {
                    videoElement.style.display = 'none';
                    videoElement.srcObject = null;
                }
            }

            track.detach().forEach(element => element.remove());
        });
        
        this.livekitRoom.on('disconnected', (reason) => {
            console.log('🔌 Room disconnected:', reason);
            this.handleDisconnection(reason);
        });

        this.livekitRoom.on('connectionQualityChanged', (quality, participant) => {
            if (participant === this.livekitRoom.localParticipant) {
                console.log('📶 Connection quality:', quality);
                // Could update UI to show connection quality
            }
        });

        this.livekitRoom.on('reconnecting', () => {
            console.log('🔄 Reconnecting to room...');
            this.updateConnectionStatus('connecting', 'Reconnecting to interview room...');
        });

        this.livekitRoom.on('reconnected', () => {
            console.log('✅ Reconnected to room');
            this.updateConnectionStatus('connected', 'Reconnected to interview room');
        });
        
        console.log('✅ Event handlers set up');
    }
    
    startAudioLevelMonitoring() {
        // Clear any existing interval
        if (this.audioLevelInterval) {
            clearInterval(this.audioLevelInterval);
        }

        this.audioLevelInterval = setInterval(() => {
            if (!this.livekitRoom || !this.isConnected) {
                return;
            }

            try {
                // Update microphone level
                const localParticipant = this.livekitRoom.localParticipant;
                if (localParticipant && localParticipant.audioTracks && typeof localParticipant.audioTracks.size === 'number' && localParticipant.audioTracks.size > 0) {
                    const micLevel = localParticipant.audioLevel * 100;
                    const micLevelEl = document.getElementById('micLevel');
                    if (micLevelEl) {
                        micLevelEl.style.width = `${Math.min(micLevel, 100)}%`;
                        
                        // Change color based on level
                        if (micLevel > 70) {
                            micLevelEl.className = 'progress-bar bg-success';
                        } else if (micLevel > 30) {
                            micLevelEl.className = 'progress-bar bg-warning';
                        } else {
                            micLevelEl.className = 'progress-bar bg-danger';
                        }
                    }
                }

                // Update AI interviewer level
                let maxAiLevel = 0;
                this.livekitRoom.remoteParticipants.forEach(participant => {
                    if (participant.identity !== this.candidateName && participant.identity !== 'unknown') {
                        maxAiLevel = Math.max(maxAiLevel, participant.audioLevel * 100);
                    }
                });

                const aiLevelEl = document.getElementById('aiLevel');
                if (aiLevelEl) {
                    aiLevelEl.style.width = `${Math.min(maxAiLevel, 100)}%`;
                }

            } catch (error) {
                console.warn('Audio level monitoring error:', error);
            }
        }, 100);

        console.log('🎵 Audio level monitoring started');
    }
    
    async disconnectFromInterview() {
        console.log('🔌 Disconnecting from interview...');

        // Clear status polling
        if (this.statusPollingInterval) {
            clearInterval(this.statusPollingInterval);
            this.statusPollingInterval = null;
        }

        try {
            if (this.livekitRoom && this.isConnected) {
                await this.livekitRoom.disconnect();
            }
        } catch (error) {
            console.error('Error during disconnect:', error);
        } finally {
            this.handleDisconnection('user_initiated');
        }
    }
    
    async handleDisconnection(reason = 'unknown') {
        console.log('🔌 Handling disconnection, reason:', reason);

        this.isConnected = false;
        this.livekitRoom = null;

        // Clean up audio monitoring
        if (this.audioLevelInterval) {
            clearInterval(this.audioLevelInterval);
            this.audioLevelInterval = null;
        }

        // Clean up status polling
        if (this.statusPollingInterval) {
            clearInterval(this.statusPollingInterval);
            this.statusPollingInterval = null;
        }

        // Reset audio levels
        const micLevelEl = document.getElementById('micLevel');
        const aiLevelEl = document.getElementById('aiLevel');
        if (micLevelEl) micLevelEl.style.width = '0%';
        if (aiLevelEl) aiLevelEl.style.width = '0%';

        // Update UI
        this.updateConnectionStatus('disconnected', 'Disconnected from interview');

        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        connectBtn.classList.remove('d-none');
        disconnectBtn.classList.add('d-none');
        connectBtn.disabled = false;

        // Send interview report via email when interview ends
        if (reason === 'user_initiated' && this.sessionData && this.sessionData.session_id) {
            try {
                console.log('📧 Sending interview report via email...');
                const response = await fetch(`/api/reports/${this.sessionData.session_id}/send`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        console.log('✅ Interview report sent successfully');
                        this.showMessage('voiceMessage', 'success', 'Interview completed! Report has been sent to HR and your email.');
                    } else {
                        console.error('❌ Failed to send report:', result.message);
                        this.showMessage('voiceMessage', 'warning', 'Interview completed, but there was an issue sending the report. Please download it manually.');
                    }
                } else {
                    console.error('❌ Report sending failed with status:', response.status);
                    this.showMessage('voiceMessage', 'warning', 'Interview completed, but there was an issue sending the report. Please download it manually.');
                }
            } catch (error) {
                console.error('❌ Error sending report:', error);
                this.showMessage('voiceMessage', 'warning', 'Interview completed, but there was an issue sending the report. Please download it manually.');
            }
        } else {
            // Show appropriate message based on reason
            if (reason === 'user_initiated') {
                this.showMessage('voiceMessage', 'info', 'You have disconnected from the interview.');
            } else {
                this.showMessage('voiceMessage', 'warning',
                    'Connection to interview room was lost. You can reconnect or the interview may be complete.');
            }
        }

        // Show results section after disconnect
        setTimeout(() => {
            this.showSection('results');
        }, 2000);
    }
    
    updateProgress(percentage, step, details) {
        const progressBar = document.getElementById('progressBar');
        const currentStep = document.getElementById('currentStep');
        const progressText = document.getElementById('progressText');
        const processingText = document.getElementById('processingText');
        
        if (progressBar) progressBar.style.width = `${percentage}%`;
        if (currentStep) currentStep.textContent = step;
        if (progressText) progressText.textContent = `${percentage}%`;
        if (processingText) processingText.textContent = details;
    }
    
    updateConnectionStatus(status, message) {
        const statusEl = document.getElementById('connectionStatus');
        if (!statusEl) return;
        
        // Remove all status classes
        statusEl.classList.remove('alert-secondary', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
        
        // Add appropriate status class and icon
        let iconClass = 'fa-wifi';
        let alertClass = 'alert-secondary';
        
        switch (status) {
            case 'connecting':
                alertClass = 'alert-info';
                iconClass = 'fa-spinner fa-spin';
                break;
            case 'connected':
                alertClass = 'alert-success';
                iconClass = 'fa-check-circle';
                break;
            case 'disconnected':
                alertClass = 'alert-warning';
                iconClass = 'fa-exclamation-triangle';
                break;
            case 'error':
                alertClass = 'alert-danger';
                iconClass = 'fa-times-circle';
                break;
        }
        
        statusEl.classList.add(alertClass);
        statusEl.innerHTML = `<i class="fas ${iconClass} me-2"></i>${message}`;
    }
    
    updateInterviewProgress(current, total) {
        const currentQuestionEl = document.getElementById('currentQuestionNum');
        const totalQuestionsEl = document.getElementById('totalQuestions');
        const progressBar = document.getElementById('interviewProgressBar');
        
        if (currentQuestionEl) currentQuestionEl.textContent = current + 1;
        if (totalQuestionsEl) totalQuestionsEl.textContent = total;
        
        if (progressBar && total > 0) {
            const percentage = Math.round((current / total) * 100);
            progressBar.style.width = `${percentage}%`;
        }
    }
    
    updateInterviewStatus(status) {
        const statusEl = document.getElementById('interviewStatus');
        if (statusEl) {
            statusEl.textContent = status;
            console.log(`Interview status updated to: ${status}`);
        }
    }
    
    showInterviewProgress() {
        const progressEl = document.getElementById('interviewProgress');
        const audioLevelsEl = document.getElementById('audioLevels');
        
        if (progressEl) progressEl.classList.remove('d-none');
        if (audioLevelsEl) audioLevelsEl.classList.remove('d-none');
    }
    
    showSection(sectionName) {
        console.log(`📱 Switching to section: ${sectionName}`);
        
        // Hide all sections
        const sections = ['setup', 'processing', 'voice', 'results'];
        sections.forEach(section => {
            const el = document.getElementById(`${section}Section`);
            if (el) {
                el.classList.add('d-none');
            }
        });
        
        // Show target section
        const targetSection = document.getElementById(`${sectionName}Section`);
        if (targetSection) {
            targetSection.classList.remove('d-none');
            // Scroll to top of section
            targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            console.error(`Section not found: ${sectionName}Section`);
        }
        
        this.currentStep = sectionName;
    }
    
    showMessage(containerId, type, message, clickable = false, clickHandler = null) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`Message container not found: ${containerId}`);
            return;
        }
        
        const iconMap = {
            'success': 'check-circle',
            'danger': 'times-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        
        const icon = iconMap[type] || 'info-circle';
        const formattedMessage = message.replace(/\n/g, '<br>');
        
        const messageHtml = `
            <div class="alert alert-${type} ${clickable ? 'alert-clickable' : ''}" 
                 ${clickable ? 'style="cursor: pointer;"' : ''}>
                <i class="fas fa-${icon} me-2"></i>
                <span>${formattedMessage}</span>
            </div>
        `;
        
        container.innerHTML = messageHtml;
        
        if (clickable && clickHandler) {
            container.querySelector('.alert').addEventListener('click', clickHandler);
        }
    }

    clearMessage(containerId) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = '';
        }
    }
    
    async notifyBackendOfConnection() {
        if (!this.sessionData || !this.sessionData.session_id) {
            console.error('Cannot notify backend: session_id is missing');
            return;
        }

        try {
            const response = await fetch(`/api/session/${this.sessionData.session_id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    status: 'in-progress',
                    connected_at: new Date().toISOString()
                })
            });

            if (response.ok) {
                console.log('✅ Backend notified of connection');
            } else {
                console.warn('⚠️ Failed to notify backend of connection');
            }
        } catch (error) {
            console.error('❌ Failed to notify backend of connection:', error);
        }
    }

    async sendReportEmail() {
        if (!this.sessionData || !this.sessionData.session_id) {
            console.error('Cannot send report email: session_id is missing');
            return;
        }

        try {
            console.log('📧 Sending interview report via email...');
            const response = await fetch(`/api/reports/${this.sessionData.session_id}/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    console.log('✅ Interview report sent successfully');
                    this.showMessage('voiceMessage', 'success', 'Interview completed! Report has been sent to HR and your email.');
                } else {
                    console.error('❌ Failed to send report:', result.message);
                    this.showMessage('voiceMessage', 'warning', 'Interview completed, but there was an issue sending the report. Please download it manually.');
                }
            } else {
                console.error('❌ Report sending failed with status:', response.status);
                this.showMessage('voiceMessage', 'warning', 'Interview completed, but there was an issue sending the report. Please download it manually.');
            }
        } catch (error) {
            console.error('❌ Error sending report:', error);
            this.showMessage('voiceMessage', 'warning', 'Interview completed, but there was an issue sending the report. Please download it manually.');
        }
    }

    async pollSessionStatus() {
        if (!this.sessionData || !this.sessionData.session_id) {
            console.error('Cannot poll session status: session_id is missing');
            return;
        }

        this.statusPollingAttempts = 0;

        const poll = async () => {
            try {
                const response = await fetch(`/api/session/${this.sessionData.session_id}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const sessionData = await response.json();
                if (sessionData.success && sessionData.session) {
                    const status = sessionData.session.status;
                    console.log(`📊 Session status: ${status} (attempt ${this.statusPollingAttempts + 1})`);

                    if (status === 'completed') {
                        console.log('✅ Interview completed, updating UI');
                        console.log('📊 Session data before update:', this.sessionData);
                        this.sessionData.status = 'completed';
                        console.log('📊 Session data after update:', this.sessionData);
                        this.showMessage('voiceMessage', 'success', 'Interview completed! Generating report...');
                        this.updateConnectionStatus('disconnected', 'Interview completed');
                        console.log('✅ UI status updated to completed');

                        // Stop polling
                        if (this.statusPollingInterval) {
                            clearInterval(this.statusPollingInterval);
                            this.statusPollingInterval = null;
                        }

                        // Send interview report via email
                        this.sendReportEmail();

                        // Show results section and download report
                        setTimeout(() => {
                            this.showSection('results');
                            this.downloadReport();
                        }, 1000);

                        return;
                    } else if (status === 'disconnected') {
                        console.log('🔌 Interview disconnected, updating UI');
                        this.sessionData.status = 'disconnected';
                        this.showMessage('voiceMessage', 'info', 'Interview session has ended.');
                        this.updateConnectionStatus('disconnected', 'Interview session ended');
                        console.log('✅ UI status updated to disconnected');

                        // Stop polling
                        if (this.statusPollingInterval) {
                            clearInterval(this.statusPollingInterval);
                            this.statusPollingInterval = null;
                        }

                        // Show results section
                        setTimeout(() => {
                            this.showSection('results');
                        }, 1000);

                        return;
                    } else if (status === 'interviewing' || status === 'in-progress') {
                        // Interview still in progress, update UI accordingly
                        this.updateConnectionStatus('connected', 'Interview in progress');
                        this.showMessage('voiceMessage', 'info', 'Interview is currently in progress...');
                    }
                }

                this.statusPollingAttempts++;
                if (this.statusPollingAttempts >= this.maxStatusPollingAttempts) {
                    console.log('⏰ Stopped polling session status after max attempts');
                    if (this.statusPollingInterval) {
                        clearInterval(this.statusPollingInterval);
                        this.statusPollingInterval = null;
                    }
                    this.showMessage('voiceMessage', 'warning', 'Interview status update timed out. Please check manually.');
                }
            } catch (error) {
                console.error('Error polling session status:', error);
                this.statusPollingAttempts++;
                if (this.statusPollingAttempts >= this.maxStatusPollingAttempts) {
                    if (this.statusPollingInterval) {
                        clearInterval(this.statusPollingInterval);
                        this.statusPollingInterval = null;
                    }
                }
            }
        };

        // Start polling every 1 second
        this.statusPollingInterval = setInterval(poll, 1000);
        // Initial poll
        poll();
    }

    async downloadReport() {
        if (!this.sessionData || !this.sessionData.session_id) {
            this.showMessage('resultsSection', 'danger', 'No session data available for report generation.');
            return;
        }

        try {
            const response = await fetch(`/api/reports/${this.sessionData.session_id}`);

            if (!response.ok) {
                throw new Error(`Report download failed: ${response.status}`);
            }

            // Get the PDF data as blob
            const pdfBlob = await response.blob();

            // Create and trigger download
            const url = URL.createObjectURL(pdfBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `interview_report_${this.sessionData.session_id.substring(0, 8)}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            console.log('📄 PDF Report downloaded successfully');

        } catch (error) {
            console.error('Report download failed:', error);
            this.showMessage('resultsSection', 'danger', `Report download failed: ${error.message}`);
        }
    }
    
    handleAvatarVideoTrack(track, participant) {
        console.log('🎥 Handling avatar video track from:', participant.identity);

        // Get the existing avatar video element from the center of the page
        const videoElement = document.getElementById('avatar-video');
        if (!videoElement) {
            console.warn('Avatar video element not found in DOM');
            return;
        }

        // Clear any existing video source
        videoElement.srcObject = null;

        // Attach the track directly to the existing video element
        track.attach(videoElement);

        // Ensure video properties are set correctly
        videoElement.autoplay = true;
        videoElement.playsinline = true;
        videoElement.muted = false; // Avatar video should have sound if needed
        videoElement.style.display = 'block';

        console.log('✅ Avatar video track attached and displayed in center');
    }

    startNewInterview() {
        console.log('🔄 Starting new interview');

        // Clear status polling
        if (this.statusPollingInterval) {
            clearInterval(this.statusPollingInterval);
            this.statusPollingInterval = null;
        }

        // Reset application state
        this.sessionData = null;
        this.isConnected = false;
        this.interviewProgress = 0;
        this.connectionRetries = 0;

        // Disconnect from any existing room
        if (this.livekitRoom) {
            try {
                this.livekitRoom.disconnect();
            } catch (e) {
                console.warn('Error disconnecting during reset:', e);
            }
            this.livekitRoom = null;
        }

        // Clear audio monitoring
        if (this.audioLevelInterval) {
            clearInterval(this.audioLevelInterval);
            this.audioLevelInterval = null;
        }

        // Hide avatar video
        const videoElement = document.getElementById('avatar-video');
        if (videoElement) {
            videoElement.style.display = 'none';
            videoElement.srcObject = null;
        }

        // Reset form
        const form = document.getElementById('setupForm');
        if (form) {
            form.reset();
        }

        // Clear all messages
        ['setupMessage', 'voiceMessage'].forEach(id => this.clearMessage(id));

        // Reset UI state
        this.updateConnectionStatus('ready', 'Ready to connect');

        // Show setup section
        this.showSection('setup');
        this.validateForm();

        console.log('✅ Application reset complete');
    }
}

// Global functions for button onclick handlers
function connectToInterview() {
    if (window.app) {
        window.app.connectToInterview();
    }
}

function disconnectFromInterview() {
    if (window.app) {
        window.app.disconnectFromInterview();
    }
}

function downloadReport() {
    if (window.app) {
        window.app.downloadReport();
    }
}

function startNewInterview() {
    if (window.app) {
        window.app.startNewInterview();
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Interview Application');
    try {
        window.app = new InterviewApp();
        console.log('✅ Application initialized successfully');
    } catch (error) {
        console.error('❌ Failed to initialize application:', error);
        
        // Show error message to user
        const statusEl = document.getElementById('systemStatus');
        if (statusEl) {
            statusEl.className = 'alert alert-danger';
            statusEl.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="fas fa-times-circle me-2"></i>
                    <div>
                        <strong>Application Failed to Start</strong><br>
                        <small>Please refresh the page. If the problem persists, contact support.</small>
                    </div>
                </div>
            `;
        }
    }
});

// Add CSS for clickable alerts
const style = document.createElement('style');
style.textContent = `
    .alert-clickable:hover {
        opacity: 0.8;
        transform: translateY(-1px);
        transition: all 0.2s ease;
    }
    
    .progress-bar {
        transition: width 0.3s ease, background-color 0.3s ease;
    }
    
    .section-transition {
        transition: opacity 0.3s ease;
    }
`;
document.head.appendChild(style);