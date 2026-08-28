// SMT Website - Client-Side Interactive Engine (Samaya Cabs style)

// --- TABS: Other Services Booking Widget ---
function switchBookingTab(serviceType) {
    const tabs = ['outstation', 'airport', 'rental'];
    
    tabs.forEach(tab => {
        const tabEl = document.getElementById(`tab-${tab}`);
        const btnEl = document.querySelector(`.pills-row button[onclick*="${tab}"]`);
        
        if (tab === serviceType) {
            tabEl.classList.add('active');
            if (btnEl) btnEl.classList.add('active');
        } else {
            tabEl.classList.remove('active');
            if (btnEl) btnEl.classList.remove('active');
        }
    });
}

// --- OUTSTATION TRIP: Toggle Return Date for Round Trip / One Way ---
function toggleReturnDate(show) {
    const returnContainer = document.getElementById('return-date-container');
    const returnInput = document.getElementById('out-return-date');
    
    if (show) {
        returnContainer.style.display = 'block';
        returnInput.required = true;
    } else {
        returnContainer.style.display = 'none';
        returnInput.required = false;
        returnInput.value = '';
    }
}

// --- AIRPORT TRIP: Adjust Location Labels ---
function setAirportLocationLabel(type) {
    const labelEl = document.getElementById('lbl-air-location');
    const inputEl = document.getElementById('air-location');
    
    if (type === 'drop') {
        labelEl.textContent = 'Drop-Off Location in City*';
        inputEl.placeholder = '📍 Address/Area in Bangalore';
    } else {
        labelEl.textContent = 'Pick-Up Location in City*';
        inputEl.placeholder = '📍 Address/Area in Bangalore';
    }
}

// --- FLEET SELECTION CONNECTIVITY ---
function selectFleetVehicle(vehicleName) {
    // Scroll to booking sections
    const isBus = vehicleName.includes('Bus') || vehicleName.includes('Urbania') || vehicleName.includes('TT');
    
    if (isBus) {
        // Switch focus to Corporate ETS
        const formEl = document.getElementById('corporate-ets');
        if (formEl) formEl.scrollIntoView({ behavior: 'smooth' });
        
        document.getElementById('ets-details').value = `Selected Fleet Vehicle: ${vehicleName}\nPreferred Route: `;
        setTimeout(() => {
            const countInput = document.getElementById('ets-commuters');
            if (countInput) countInput.focus();
        }, 500);
    } else {
        // Switch focus to Other Services -> Outstation
        const formEl = document.getElementById('other-services');
        if (formEl) formEl.scrollIntoView({ behavior: 'smooth' });
        
        switchBookingTab('outstation');
        // Pre-fill Outstation drop or details
        const detailsField = `Selected Vehicle: ${vehicleName}`;
        // Set some dummy target or just focus pickup
        setTimeout(() => {
            const pickInput = document.getElementById('out-pickup');
            if (pickInput) {
                pickInput.focus();
                // Add a placeholder notification in details or memory
                console.log(detailsField);
            }
        }, 500);
    }
}

// --- FORM API SUBMISSIONS ---
async function handleFormSubmit(formId, getPayloadFn) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        try {
            const payload = getPayloadFn();
            const response = await fetch('/api/inquiries', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.ok) {
                alert("Thank you! Your booking request/inquiry has been submitted successfully to SMT. Our supervisors will contact you shortly.");
                form.reset();
                // If outstation, reset return date visibility
                if (formId === 'outstation-form') {
                    toggleReturnDate(true);
                }
            } else {
                alert(`Submission failed: ${result.error || "Please verify fields"}`);
            }
        } catch (err) {
            console.error("API submission error:", err);
            alert("Failed to connect to the SMT server. Please ensure the local backend is running.");
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Wire up forms on DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
    // 1. Corporate ETS Form Submit
    handleFormSubmit('corporate-ets-form', () => {
        return {
            name: document.getElementById('ets-name').value,
            company: document.getElementById('ets-company').value,
            email: document.getElementById('ets-email').value,
            phone: document.getElementById('ets-phone').value,
            service_type: 'Corporate ETS',
            employee_count: parseInt(document.getElementById('ets-commuters').value) || 0,
            details: document.getElementById('ets-details').value
        };
    });

    // 2. Outstation Form Submit
    handleFormSubmit('outstation-form', () => {
        const tripType = document.querySelector('input[name="outstation_type"]:checked').value;
        const pickup = document.getElementById('out-pickup').value;
        const drop = document.getElementById('out-drop').value;
        const pDate = document.getElementById('out-date').value;
        const rDate = document.getElementById('out-return-date').value;
        const pTime = document.getElementById('out-time').value;

        return {
            name: document.getElementById('out-name').value,
            email: document.getElementById('out-email').value,
            phone: document.getElementById('out-phone').value,
            company: 'Retail client (Outstation)',
            service_type: 'Outstation',
            employee_count: 0,
            details: `Trip Type: ${tripType}\nPickup: ${pickup}\nDrop: ${drop}\nPickup Date: ${pDate}\nReturn Date: ${rDate || 'N/A'}\nTime: ${pTime}`
        };
    });

    // 3. Airport Form Submit
    handleFormSubmit('airport-form', () => {
        const tripType = document.querySelector('input[name="airport_trip_type"]:checked').value;
        const terminal = document.getElementById('air-terminal').value;
        const cityLoc = document.getElementById('air-location').value;
        const pDate = document.getElementById('air-date').value;
        const pTime = document.getElementById('air-time').value;

        return {
            name: document.getElementById('air-name').value,
            email: document.getElementById('air-email').value,
            phone: document.getElementById('air-phone').value,
            company: 'Retail client (Airport)',
            service_type: 'Airport Transfer',
            employee_count: 0,
            details: `Trip Type: Airport ${tripType}\nTerminal: ${terminal}\nCity Address: ${cityLoc}\nPickup Date: ${pDate}\nTime: ${pTime}`
        };
    });

    // 4. Hourly Rental Form Submit
    handleFormSubmit('rental-form', () => {
        const pickup = document.getElementById('ren-pickup').value;
        const packageSelected = document.getElementById('ren-package').value;
        const pDate = document.getElementById('ren-date').value;
        const pTime = document.getElementById('ren-time').value;

        return {
            name: document.getElementById('ren-name').value,
            email: document.getElementById('ren-email').value,
            phone: document.getElementById('ren-phone').value,
            company: 'Retail client (Rental)',
            service_type: 'Hourly Rental',
            employee_count: 0,
            details: `City: Bangalore\nPickup Address: ${pickup}\nPackage: ${packageSelected}\nPickup Date: ${pDate}\nTime: ${pTime}`
        };
    });

    // Initialize Canvas backgrounds and animations
    initBackgroundNetwork();
    initRoadScene();

    // Mobile Menu Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const navbarMenu = document.getElementById('navbar-menu');
    if (mobileMenuBtn && navbarMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            navbarMenu.classList.toggle('open');
            mobileMenuBtn.textContent = navbarMenu.classList.contains('open') ? '✕' : '☰';
        });
        
        // Close menu when clicking a link
        navbarMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navbarMenu.classList.remove('open');
                mobileMenuBtn.textContent = '☰';
            });
        });
    }

    // Laptop & Mobile View Preview Toggle Logic
    const btnLaptop = document.getElementById('btn-laptop-view');
    const btnMobile = document.getElementById('btn-mobile-view');
    if (btnLaptop && btnMobile) {
        btnLaptop.addEventListener('click', () => {
            document.body.classList.remove('preview-mode-mobile');
            btnLaptop.classList.add('active');
            btnMobile.classList.remove('active');
            window.dispatchEvent(new Event('resize'));
        });
        btnMobile.addEventListener('click', () => {
            document.body.classList.add('preview-mode-mobile');
            btnMobile.classList.add('active');
            btnLaptop.classList.remove('active');
            window.dispatchEvent(new Event('resize'));
        });
    }

    // Initialize Autocomplete for location fields
    initLocationAutocomplete('out-pickup');
    initLocationAutocomplete('out-drop');
    initLocationAutocomplete('air-location');
    initLocationAutocomplete('ren-pickup');
});

// --- HELPDESK FLOATING CHAT WIDGET ---
let chatSessionId = 'smt-session-' + Math.random().toString(36).substring(2, 9);

function toggleChat() {
    const windowEl = document.getElementById('chat-window');
    windowEl.classList.toggle('open');
}

function handleChatKey(event) {
    if (event.key === 'Enter') {
        sendChatMessage();
    }
}

async function sendChatMessage(customMsg = null) {
    const inputEl = document.getElementById('chat-input');
    const msgText = customMsg ? customMsg : inputEl.value.trim();
    
    if (!msgText) return;

    if (!customMsg) {
        inputEl.value = '';
    }

    appendChatBubble(msgText, 'user');

    // Add thinking bubble
    const typingId = appendChatBubble('Thinking...', 'bot typing');

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: msgText,
                session_id: chatSessionId
            })
        });

        const result = await response.json();
        
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        if (response.ok) {
            appendChatBubble(result.response, 'bot');
        } else {
            appendChatBubble("Sorry, I had trouble processing that request. Please try again.", 'bot');
        }
    } catch (err) {
        console.error("Chat error:", err);
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        appendChatBubble("I'm having trouble connecting to SMT support systems. Please verify the Flask server is running.", 'bot');
    }
}

function sendQuickReply(replyText) {
    sendChatMessage(replyText);
}

function appendChatBubble(text, sender) {
    const chatMsgs = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    const bubbleId = 'bubble-' + Math.random().toString(36).substring(2, 9);
    
    bubble.id = bubbleId;
    bubble.className = `chat-bubble ${sender}`;
    bubble.innerHTML = text.replace(/\n/g, '<br>');
    
    chatMsgs.appendChild(bubble);
    chatMsgs.scrollTop = chatMsgs.scrollHeight;

    return bubbleId;
}

// --- DYNAMIC BACKGROUND NETWORK CANVAS ---
function initBackgroundNetwork() {
    const canvas = document.getElementById('routing-network-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let particles = [];
    const maxParticles = 65;
    const connectionDistance = 120;
    let mouse = { x: null, y: null, radius: 150 };

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    window.addEventListener('mouseleave', () => {
        mouse.x = null;
        mouse.y = null;
    });

    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * 0.5;
            this.vy = (Math.random() - 0.5) * 0.5;
            this.radius = Math.random() * 2 + 1.2;
            this.color = Math.random() > 0.45 ? 'rgba(30, 27, 75, 0.25)' : 'rgba(245, 158, 11, 0.25)';
        }

        update() {
            if (this.x < 0 || this.x > canvas.width) this.vx = -this.vx;
            if (this.y < 0 || this.y > canvas.height) this.vy = -this.vy;

            this.x += this.vx;
            this.y += this.vy;

            if (mouse.x !== null && mouse.y !== null) {
                const dx = mouse.x - this.x;
                const dy = mouse.y - this.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < mouse.radius) {
                    const force = (mouse.radius - dist) / mouse.radius;
                    this.x += (dx / dist) * force * 0.8;
                    this.y += (dy / dist) * force * 0.8;
                }
            }
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.fill();
        }
    }

    for (let i = 0; i < maxParticles; i++) {
        particles.push(new Particle());
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < particles.length; i++) {
            particles[i].update();
            particles[i].draw();

            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < connectionDistance) {
                    const alpha = (1 - dist / connectionDistance) * 0.12;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(30, 27, 75, ${alpha})`;
                    ctx.lineWidth = 0.8;
                    ctx.stroke();
                }
            }
        }

        requestAnimationFrame(animate);
    }

    animate();
}

// --- ROAD SCENE REVEAL ENGINE ---
function initRoadScene() {
    const section = document.getElementById('road-scene');
    if (!section) return;

    // Set scroll handler for header sticky shrink styling
    window.addEventListener('scroll', () => {
        const header = document.querySelector('.jmr-header');
        if (header) {
            if (window.scrollY > 80) {
                header.classList.add('shrink');
            } else {
                header.classList.remove('shrink');
            }
        }
    });
}

// --- LOCATION AUTOCOMPLETE ENGINE ---
function initLocationAutocomplete(inputId) {
    const inputEl = document.getElementById(inputId);
    if (!inputEl) return;

    const parentEl = inputEl.parentElement;
    parentEl.style.position = 'relative';

    let suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'autocomplete-suggestions';
    suggestionsContainer.style.display = 'none';
    parentEl.appendChild(suggestionsContainer);

    let debounceTimer;

    inputEl.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const query = inputEl.value.trim();

        if (query.length < 3) {
            suggestionsContainer.style.display = 'none';
            suggestionsContainer.innerHTML = '';
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const response = await fetch(`/api/places-autocomplete?q=${encodeURIComponent(query)}`);
                if (!response.ok) throw new Error('Network response not ok');
                const data = await response.json();

                if (data.length === 0) {
                    suggestionsContainer.style.display = 'none';
                    suggestionsContainer.innerHTML = '';
                    return;
                }

                suggestionsContainer.innerHTML = '';
                data.forEach(item => {
                    const suggestionEl = document.createElement('div');
                    suggestionEl.className = 'autocomplete-suggestion';
                    suggestionEl.textContent = item.display_name;
                    suggestionEl.addEventListener('click', () => {
                        inputEl.value = item.display_name;
                        suggestionsContainer.style.display = 'none';
                        suggestionsContainer.innerHTML = '';
                        inputEl.dispatchEvent(new Event('input'));
                    });
                    suggestionsContainer.appendChild(suggestionEl);
                });
                suggestionsContainer.style.display = 'block';
            } catch (err) {
                console.error('Failed to load places suggestions:', err);
            }
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (e.target !== inputEl && e.target !== suggestionsContainer && !suggestionsContainer.contains(e.target)) {
            suggestionsContainer.style.display = 'none';
        }
    });

    inputEl.addEventListener('focus', () => {
        if (suggestionsContainer.children.length > 0) {
            suggestionsContainer.style.display = 'block';
        }
    });
}
