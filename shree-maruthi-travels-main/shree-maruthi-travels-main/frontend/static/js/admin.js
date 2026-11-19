// SMT Supervisor Dashboard - Administrative Engine

let allInquiries = [];
let smtToken = sessionStorage.getItem('smt_token');
let currentCabIdForDocs = null;
let staffSession = { role: 'staff', can_od: false, email: null };

function applyStaffSession(me) {
    staffSession = {
        email: me.email || null,
        role: me.role || 'staff',
        can_od: !!me.can_od,
    };
    smtToken = smtToken || 'session';
    sessionStorage.setItem('smt_token', smtToken);
    const nav = document.getElementById('od-workspace-nav');
    if (nav) nav.style.display = staffSession.can_od ? '' : 'none';
    const odCard = document.getElementById('od-workspace-card');
    if (odCard) odCard.style.display = staffSession.can_od ? '' : 'none';
    const label = document.getElementById('staff-session-label');
    if (label) {
        label.textContent = staffSession.email || '';
    }
    const settingsLabel = document.getElementById('settings-session-label');
    if (settingsLabel) {
        settingsLabel.textContent = staffSession.email || 'Staff session';
    }
    const avatar = document.querySelector('.portal-avatar');
    if (avatar) {
        const ch = (staffSession.email || 'A').trim().charAt(0).toUpperCase();
        avatar.textContent = ch || 'A';
    }
    const hint = document.getElementById('google-login-hint');
    if (hint) hint.style.display = me.google_login ? 'none' : 'block';
}

function showLoginOverlay(me) {
    document.getElementById('admin-login-overlay').classList.remove('hidden');
    document.getElementById('admin-workspace').style.display = 'none';
    const hint = document.getElementById('google-login-hint');
    const localForm = document.getElementById('local-login-form');
    const googleBtn = document.getElementById('google-login-btn');
    const emails = (me && me.local_staff) || [];
    if (localForm && emails.length) {
        const select = document.getElementById('local-staff-email');
        select.replaceChildren();
        emails.forEach((email) => {
            const option = document.createElement('option');
            option.value = email;
            option.textContent = email;
            if (email.indexOf('abhishek') === 0) option.selected = true;
            select.appendChild(option);
        });
        localForm.style.display = 'block';
        if (googleBtn) googleBtn.style.display = 'none';
        if (hint) hint.style.display = 'none';
    } else if (hint) {
        hint.style.display = me && me.google_login ? 'none' : 'block';
    }
    const params = new URLSearchParams(window.location.search);
    const errorEl = document.getElementById('login-error');
    if (params.get('login_error') === 'not_allowed') {
        errorEl.style.display = 'block';
        errorEl.textContent = 'This Gmail is not on the SMT staff list.';
    } else if (params.get('login_error') === 'google') {
        errorEl.style.display = 'block';
        errorEl.textContent = 'Google Sign-In failed. Use an approved SMT Gmail.';
    }
}

function revealWorkspace(me) {
    applyStaffSession(me || {});
    document.getElementById('admin-login-overlay').classList.add('hidden');
    document.getElementById('admin-workspace').style.display = 'flex';
    const hash = (window.location.hash || '').replace('#', '');
    const allowed = ['home', 'datasource', 'inquiries', 'cabs', 'drivers', 'pg-drivers', 'pg-vehicles', 'companies', 'ev', 'tracking', 'settings', 'help'];
    switchTab(allowed.includes(hash) ? hash : 'home');
}

window.onload = async function() {
    try {
        const response = await fetch('/api/admin/me', { credentials: 'same-origin' });
        const me = await response.json();
        if (response.ok && me.authenticated) {
            revealWorkspace(me);
            return;
        }
        showLoginOverlay(me);
    } catch (err) {
        showLoginOverlay({ google_login: false });
    }
};

function adminLogout() {
    sessionStorage.removeItem('smt_token');
    smtToken = null;
    staffSession = { role: 'staff', can_od: false, email: null };
    fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' }).finally(() => {
        window.location.href = '/admin';
    });
}

function toggleAdminNav() {
    const workspace = document.getElementById('admin-workspace');
    if (workspace) workspace.classList.toggle('nav-open');
}

function closeAdminNav() {
    const workspace = document.getElementById('admin-workspace');
    if (workspace) workspace.classList.remove('nav-open');
}

const DATASOURCE_TABS = ['datasource', 'inquiries', 'cabs', 'drivers', 'pg-drivers', 'pg-vehicles', 'companies', 'ev'];

// --- TAB SWITCHER ---
function switchTab(tabId) {
    if (!smtToken) return;

    document.querySelectorAll('.admin-tab-content').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
    });
    document.querySelectorAll('.portal-side-link, .admin-nav-menu button, .admin-nav-menu a').forEach(el => {
        el.classList.remove('active');
    });
    document.querySelectorAll('.admin-nav-drop').forEach(el => {
        el.classList.remove('is-current');
    });

    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }

    const targetBtn = document.getElementById(`btn-tab-${tabId}`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }

    if (tabId === 'tracking') {
        const ets = document.querySelector('[data-group="ets"]');
        if (ets) ets.classList.add('is-current');
    }
    if (DATASOURCE_TABS.includes(tabId)) {
        const ds = document.querySelector('[data-group="datasource"]');
        if (ds) ds.classList.add('is-current');
        const dsBtn = document.getElementById('btn-tab-datasource');
        if (dsBtn) dsBtn.classList.add('active');
    }

    closeAdminNav();
    if (history.replaceState) {
        history.replaceState(null, '', tabId === 'home' ? '/admin' : `/admin#${tabId}`);
    }

    if (tabId === 'inquiries') {
        fetchDashboardData();
    } else if (tabId === 'cabs') {
        fetchCabs();
    } else if (tabId === 'drivers') {
        fetchDrivers();
    } else if (tabId === 'pg-drivers') {
        fetchPgDrivers();
    } else if (tabId === 'pg-vehicles') {
        fetchPgVehicles();
    } else if (tabId === 'companies') {
        fetchCompanies();
    } else if (tabId === 'ev') {
        fetchEvCabs();
    } else if (tabId === 'tracking') {
        fetchLiveTrips();
    }
}

window.addEventListener('hashchange', () => {
    if (!smtToken) return;
    const hash = (window.location.hash || '').replace('#', '');
    const allowed = ['home', 'datasource', 'inquiries', 'cabs', 'drivers', 'pg-drivers', 'pg-vehicles', 'companies', 'ev', 'tracking', 'settings', 'help'];
    if (!allowed.includes(hash)) return;
    const current = document.querySelector('.admin-tab-content.active');
    if (current && current.id === `tab-${hash}`) return;
    switchTab(hash);
});

// --- DATA FETCHING (INQUIRIES) ---
async function fetchDashboardData() {
    if (!smtToken) return;

    try {
        // Fetch Stats
        const statsRes = await fetch('/api/stats', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        
        // Fetch Inquiries
        const inquiriesRes = await fetch('/api/inquiries', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });

        if (statsRes.status === 401 || inquiriesRes.status === 401) {
            adminLogout();
            alert("Session expired. Please log in again.");
            return;
        }

        const stats = await statsRes.json();
        allInquiries = await inquiriesRes.json();

        // Update stats widgets
        document.getElementById('stat-total').textContent = stats.total;
        document.getElementById('stat-pending').textContent = stats.pending;
        document.getElementById('stat-in-progress').textContent = stats.in_progress;
        document.getElementById('stat-completed').textContent = stats.completed;
        const zohoEl = document.getElementById('zoho-status');
        if (zohoEl) {
            zohoEl.textContent = stats.zoho_connected ? 'Zoho Sheet: connected' : 'Zoho Sheet: not connected (inquiries stay on this server)';
            zohoEl.style.color = stats.zoho_connected ? '#059669' : '#b45309';
        }

        filterInquiries();
    } catch (err) {
        console.error("Fetch dashboard error:", err);
    }
}

function renderInquiries(list) {
    const tableBody = document.getElementById('inquiries-table-body');
    tableBody.innerHTML = '';

    if (list.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No inquiries found matching criteria.</td></tr>`;
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');
        
        let badgeClass = 'pending';
        if (item.status === 'In Progress') badgeClass = 'in-progress';
        if (item.status === 'Completed') badgeClass = 'completed';

        tr.innerHTML = `
            <td>
                <strong style="color: var(--text-primary); font-size: 0.95rem;">${item.name}</strong>
                ${item.company ? `<div style="font-size: 0.75rem; color: var(--accent);">${item.company}</div>` : ''}
            </td>
            <td>
                <div style="font-size: 0.85rem;">📞 ${item.phone}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">✉️ ${item.email}</div>
            </td>
            <td>
                <span style="font-weight: 500;">${item.service_type}</span>
            </td>
            <td style="text-align: center;">
                <span style="font-family: var(--font-heading); font-weight: 600;">${item.employee_count > 0 ? item.employee_count : '-'}</span>
            </td>
            <td>
                <div style="max-width: 320px; font-size: 0.8rem; line-height: 1.4; color: var(--text-secondary); white-space: pre-wrap;">${item.details || 'N/A'}</div>
            </td>
            <td style="font-size: 0.8rem; color: var(--text-muted);">
                ${item.created_at}
            </td>
            <td>
                <select class="status-select" onchange="updateInquiryStatus(${item.id}, this.value)">
                    <option value="Pending" ${item.status === 'Pending' ? 'selected' : ''}>Pending</option>
                    <option value="In Progress" ${item.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                    <option value="Completed" ${item.status === 'Completed' ? 'selected' : ''}>Completed</option>
                </select>
                <div style="margin-top: 0.4rem;">
                    <span class="status-badge ${badgeClass}">${item.status}</span>
                </div>
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

async function updateInquiryStatus(id, newStatus) {
    if (!smtToken) return;

    try {
        const response = await fetch(`/api/inquiries/${id}/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (response.ok) {
            fetchDashboardData();
        } else {
            const errResult = await response.json();
            alert(`Failed to update status: ${errResult.error}`);
        }
    } catch (err) {
        console.error("Status update error:", err);
    }
}

function filterInquiries() {
    const searchQuery = document.getElementById('admin-search-input').value.toLowerCase().trim();
    const filterStatus = document.getElementById('admin-filter-select').value;

    const filtered = allInquiries.filter(item => {
        const matchStatus = (filterStatus === 'all' || item.status === filterStatus);
        const matchSearch = (
            item.name.toLowerCase().includes(searchQuery) ||
            item.email.toLowerCase().includes(searchQuery) ||
            item.phone.toLowerCase().includes(searchQuery) ||
            item.company.toLowerCase().includes(searchQuery) ||
            item.service_type.toLowerCase().includes(searchQuery) ||
            (item.details && item.details.toLowerCase().includes(searchQuery))
        );
        return matchStatus && matchSearch;
    });

    renderInquiries(filtered);
}

// --- MODAL UTILITIES ---
function showAdminModal(title, htmlContent) {
    document.getElementById('admin-modal-title').textContent = title;
    document.getElementById('admin-modal-body').innerHTML = htmlContent;
    document.getElementById('admin-modal-overlay').style.display = 'flex';
}

function closeAdminModal() {
    document.getElementById('admin-modal-overlay').style.display = 'none';
    document.getElementById('admin-modal-body').innerHTML = '';
}

// --- CABS MANAGEMENT ---
async function fetchCabs() {
    if (!smtToken) return;
    const tbody = document.getElementById('cabs-table-body');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Syncing fleet records...</td></tr>`;

    try {
        const res = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch cabs");
        const cabs = await res.json();
        
        tbody.innerHTML = '';
        if (cabs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No vehicles registered. Click 'Add New Cab' to start.</td></tr>`;
            return;
        }

        for (const cab of cabs) {
            const tr = document.createElement('tr');
            
            // Asynchronously query doc warning status badge
            const docStatus = await getCabDocumentsStatus(cab.id);
            const evBadge = cab.is_ev ? `<span class="badge-ev" style="margin-left: 0.5rem;">EV</span>` : '';
            
            tr.innerHTML = `
                <td>
                    <strong style="color: var(--text-primary); font-size: 0.95rem;">${cab.reg_number}</strong>
                    ${evBadge}
                </td>
                <td>${cab.model}</td>
                <td>${cab.capacity} Seater</td>
                <td>${cab.fuel_type}</td>
                <td>
                    <span class="status-badge ${cab.status === 'Active' ? 'completed' : cab.status === 'Maintenance' ? 'pending' : 'expired'}">${cab.status}</span>
                </td>
                <td>
                    <span class="doc-badge ${docStatus.class}">${docStatus.text}</span>
                </td>
                <td>
                    <button class="status-select" style="margin-right: 0.25rem;" onclick="manageCabDocuments(${cab.id}, '${cab.reg_number}')">📄 Docs</button>
                    <button class="status-select" style="margin-right: 0.25rem;" onclick="showEditCabModal(${JSON.stringify(cab).replace(/"/g, '&quot;')})">Edit</button>
                    <button class="status-select" style="color: #ef4444;" onclick="deleteCab(${cab.id})">Del</button>
                </td>
            `;
            tbody.appendChild(tr);
        }
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444;">Error syncing fleet database records.</td></tr>`;
    }
}

async function getCabDocumentsStatus(cabId) {
    try {
        const res = await fetch(`/api/admin/cabs/${cabId}/documents`, {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (!res.ok) return { text: 'No Docs', class: 'warning' };
        const docs = await res.json();
        if (docs.length === 0) return { text: 'No Docs', class: 'warning' };
        
        const now = new Date();
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(now.getDate() + 30);
        
        let status = { text: 'Valid', class: 'completed' };
        
        for (const doc of docs) {
            const expDate = new Date(doc.expiry_date);
            if (expDate < now) {
                return { text: 'Expired', class: 'expired' };
            } else if (expDate <= thirtyDaysLater) {
                status = { text: 'Expiring Soon', class: 'warning' };
            }
        }
        return status;
    } catch (err) {
        return { text: 'Error', class: 'expired' };
    }
}

function showAddCabModal() {
    const html = `
        <form id="cab-form" onsubmit="saveCab(event)">
            <input type="hidden" id="form-cab-id" value="">
            <div class="form-group-custom">
                <label>Registration Number*</label>
                <input type="text" id="cab-reg" class="form-control-custom" placeholder="e.g. KA-05-MB-1234" required>
            </div>
            <div class="form-group-custom">
                <label>Vehicle Model*</label>
                <input type="text" id="cab-model" class="form-control-custom" placeholder="e.g. Toyota Innova" required>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Seating Capacity*</label>
                    <input type="number" id="cab-capacity" class="form-control-custom" min="1" value="4" required>
                </div>
                <div class="form-group-custom">
                    <label>Fuel Type*</label>
                    <select id="cab-fuel" class="form-control-custom" onchange="toggleEvFields(this.value)" required>
                        <option value="Diesel">Diesel</option>
                        <option value="Petrol">Petrol</option>
                        <option value="CNG">CNG</option>
                        <option value="EV">EV (Electric)</option>
                    </select>
                </div>
            </div>
            <div class="form-group-custom">
                <label>Status</label>
                <select id="cab-status" class="form-control-custom">
                    <option value="Active">Active</option>
                    <option value="Maintenance">Maintenance</option>
                    <option value="Inactive">Inactive</option>
                </select>
            </div>
            <div id="ev-fields" style="display: none; border-top: 1px dashed var(--border-color); padding-top: 1rem; margin-top: 1rem;">
                <h4 style="font-size: 0.95rem; margin-bottom: 1rem; color: var(--primary);">EV Fleet Parameters</h4>
                <div class="form-group-custom">
                    <label>Battery Capacity (e.g. 26 kWh)</label>
                    <input type="text" id="cab-battery" class="form-control-custom" placeholder="e.g. 26 kWh">
                </div>
                <div class="form-grid-2">
                    <div class="form-group-custom">
                        <label>Charge Status (SOC %)</label>
                        <input type="number" id="cab-charge" class="form-control-custom" min="0" max="100" placeholder="e.g. 80">
                    </div>
                    <div class="form-group-custom">
                        <label>Remaining Est. Range (KM)</label>
                        <input type="number" id="cab-range" class="form-control-custom" min="0" placeholder="e.g. 150">
                    </div>
                </div>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Save Vehicle</button>
        </form>
    `;
    showAdminModal("Add Vehicle Registry", html);
}

function showEditCabModal(cab) {
    showAddCabModal();
    document.getElementById('admin-modal-title').textContent = "Modify Vehicle Details";
    document.getElementById('form-cab-id').value = cab.id;
    document.getElementById('cab-reg').value = cab.reg_number;
    document.getElementById('cab-model').value = cab.model;
    document.getElementById('cab-capacity').value = cab.capacity;
    document.getElementById('cab-fuel').value = cab.fuel_type;
    document.getElementById('cab-status').value = cab.status;
    
    if (cab.fuel_type === 'EV') {
        toggleEvFields('EV');
        document.getElementById('cab-battery').value = cab.battery_capacity || '';
        document.getElementById('cab-charge').value = cab.charge_status !== null ? cab.charge_status : '';
        document.getElementById('cab-range').value = cab.range_km !== null ? cab.range_km : '';
    }
}

function toggleEvFields(value) {
    const evFields = document.getElementById('ev-fields');
    if (evFields) {
        if (value === 'EV') {
            evFields.style.display = 'block';
        } else {
            evFields.style.display = 'none';
        }
    }
}

async function saveCab(event) {
    event.preventDefault();
    if (!smtToken) return;

    const cabId = document.getElementById('form-cab-id').value;
    const payload = {
        reg_number: document.getElementById('cab-reg').value.trim(),
        model: document.getElementById('cab-model').value.trim(),
        capacity: document.getElementById('cab-capacity').value,
        fuel_type: document.getElementById('cab-fuel').value,
        status: document.getElementById('cab-status').value,
        is_ev: document.getElementById('cab-fuel').value === 'EV' ? 1 : 0,
        battery_capacity: document.getElementById('cab-battery') ? document.getElementById('cab-battery').value.trim() : null,
        charge_status: document.getElementById('cab-charge') ? document.getElementById('cab-charge').value : null,
        range_km: document.getElementById('cab-range') ? document.getElementById('cab-range').value : null
    };

    const url = cabId ? `/api/admin/cabs/${cabId}` : '/api/admin/cabs';
    const method = cabId ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
            closeAdminModal();
            fetchCabs();
        } else {
            alert(result.error || "Failed to save cab.");
        }
    } catch (err) {
        console.error("Save Cab Error:", err);
    }
}

async function deleteCab(cabId) {
    if (!confirm("Are you sure you want to remove this vehicle? All related assignments and documents will be deleted.")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/cabs/${cabId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchCabs();
        } else {
            alert("Failed to delete vehicle.");
        }
    } catch (err) {
        console.error("Delete Cab Error:", err);
    }
}

// --- DOCUMENT SUB-MANAGEMENT ---
async function manageCabDocuments(cabId, regNum) {
    currentCabIdForDocs = cabId;
    const html = `
        <div style="margin-bottom: 2rem;">
            <h4 style="font-size: 0.95rem; margin-bottom: 1rem; color: var(--primary);">Legal Documents - ${regNum}</h4>
            <div id="docs-list-container">
                <p style="color: var(--text-muted); font-size: 0.85rem;">Retrieving documents...</p>
            </div>
        </div>
        
        <form id="doc-form" onsubmit="saveDocument(event)" style="border-top: 1px solid var(--border-color); padding-top: 1.5rem;">
            <h4 style="font-size: 0.95rem; margin-bottom: 1rem; color: var(--primary);">Add Legal Document</h4>
            <div class="form-group-custom">
                <label>Document Category*</label>
                <select id="doc-type" class="form-control-custom" required>
                    <option value="Insurance">Insurance Policy</option>
                    <option value="Permit">National Permit</option>
                    <option value="Fitness">Fitness Certificate</option>
                    <option value="Road Tax">Road Tax Certificate</option>
                </select>
            </div>
            <div class="form-group-custom">
                <label>Certificate / Document Number*</label>
                <input type="text" id="doc-number" class="form-control-custom" placeholder="e.g. INS-998822" required>
            </div>
            <div class="form-group-custom">
                <label>Expiration Date*</label>
                <input type="date" id="doc-expiry" class="form-control-custom" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1rem;">Upload Document</button>
        </form>
    `;
    showAdminModal("Manage Cabs Documents", html);
    loadCabDocuments(cabId);
}

async function loadCabDocuments(cabId) {
    if (!smtToken) return;
    const container = document.getElementById('docs-list-container');
    
    try {
        const res = await fetch(`/api/admin/cabs/${cabId}/documents`, {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const docs = await res.json();
        
        container.innerHTML = '';
        if (docs.length === 0) {
            container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 1rem 0;">No documents associated with this vehicle.</p>`;
            return;
        }

        const now = new Date();
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(now.getDate() + 30);

        docs.forEach(doc => {
            const expDate = new Date(doc.expiry_date);
            let badgeClass = 'valid';
            let badgeText = 'Valid';

            if (expDate < now) {
                badgeClass = 'expired';
                badgeText = 'Expired';
            } else if (expDate <= thirtyDaysLater) {
                badgeClass = 'warning';
                badgeText = 'Expiring Soon';
            }

            const div = document.createElement('div');
            div.className = 'doc-item-row';
            div.innerHTML = `
                <div class="doc-details">
                    <span class="doc-name">${doc.doc_type}</span>
                    <span class="doc-number">No: ${doc.doc_number}</span>
                    <span class="doc-expiry">Expires: ${doc.expiry_date}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span class="doc-badge ${badgeClass}">${badgeText}</span>
                    <button class="status-select" style="color: #ef4444;" onclick="deleteDocument(${doc.id})">Delete</button>
                </div>
            `;
            container.appendChild(div);
        });
    } catch (err) {
        console.error("Load Documents error:", err);
    }
}

async function saveDocument(event) {
    event.preventDefault();
    if (!smtToken || !currentCabIdForDocs) return;

    const payload = {
        doc_type: document.getElementById('doc-type').value,
        doc_number: document.getElementById('doc-number').value.trim(),
        expiry_date: document.getElementById('doc-expiry').value
    };

    try {
        const res = await fetch(`/api/admin/cabs/${currentCabIdForDocs}/documents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            document.getElementById('doc-number').value = '';
            document.getElementById('doc-expiry').value = '';
            loadCabDocuments(currentCabIdForDocs);
            fetchCabs(); // Refresh parent table list
        } else {
            alert("Failed to save document.");
        }
    } catch (err) {
        console.error("Save Document Error:", err);
    }
}

async function deleteDocument(docId) {
    if (!confirm("Remove this document record?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/documents/${docId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            loadCabDocuments(currentCabIdForDocs);
            fetchCabs(); // Refresh parent table list
        } else {
            alert("Failed to delete document.");
        }
    } catch (err) {
        console.error("Delete Document Error:", err);
    }
}

// --- DRIVER MANAGEMENT ---
async function fetchDrivers() {
    if (!smtToken) return;
    const tbody = document.getElementById('drivers-table-body');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Syncing staff database...</td></tr>`;

    try {
        const res = await fetch('/api/admin/drivers', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const drivers = await res.json();
        
        tbody.innerHTML = '';
        if (drivers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No drivers registered. Click 'Add New Driver' to start.</td></tr>`;
            return;
        }

        const now = new Date();
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(now.getDate() + 30);

        drivers.forEach(driver => {
            const tr = document.createElement('tr');
            
            const expDate = new Date(driver.license_expiry);
            let licenseAlert = '';
            if (expDate < now) {
                licenseAlert = ` <span class="doc-badge expired">Expired</span>`;
            } else if (expDate <= thirtyDaysLater) {
                licenseAlert = ` <span class="doc-badge warning">Expiring</span>`;
            }

            tr.innerHTML = `
                <td><strong style="color: var(--text-primary); font-size: 0.95rem;">${driver.name}</strong></td>
                <td>${driver.phone}</td>
                <td><code>${driver.license_number}</code></td>
                <td>${driver.license_expiry}${licenseAlert}</td>
                <td>
                    ${driver.assigned_cab_id ? `<strong>${driver.cab_reg}</strong> <span style="font-size:0.75rem; color: var(--text-secondary);">(${driver.cab_model})</span>` : '<span style="color: var(--text-muted); font-size:0.8rem;">Unassigned</span>'}
                </td>
                <td>
                    <span class="status-badge ${driver.status === 'Active' ? 'completed' : 'expired'}">${driver.status}</span>
                </td>
                <td>
                    <button class="status-select" style="margin-right: 0.25rem;" onclick='showEditDriverModal(${JSON.stringify(driver).replace(/'/g, "\\'")})'>Edit</button>
                    <button class="status-select" style="color: #ef4444;" onclick="deleteDriver(${driver.id})">Del</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444;">Error syncing driver database.</td></tr>`;
    }
}

async function showAddDriverModal() {
    if (!smtToken) return;

    try {
        const cabsRes = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const cabs = await cabsRes.json();
        
        let cabOptions = '<option value="None">None (Unassigned)</option>';
        cabs.forEach(cab => {
            cabOptions += `<option value="${cab.id}">${cab.reg_number} - ${cab.model}</option>`;
        });

        const html = `
            <form id="driver-form" onsubmit="saveDriver(event)">
                <input type="hidden" id="form-driver-id" value="">
                <div class="form-group-custom">
                    <label>Driver Full Name*</label>
                    <input type="text" id="driver-name" class="form-control-custom" placeholder="e.g. Ramesh Kumar" required>
                </div>
                <div class="form-group-custom">
                    <label>Mobile Number*</label>
                    <input type="text" id="driver-phone" class="form-control-custom" placeholder="e.g. +91 9845012345" required>
                </div>
                <div class="form-group-custom">
                    <label>Driving License Number*</label>
                    <input type="text" id="driver-license" class="form-control-custom" placeholder="e.g. DL-KA05202..." required>
                </div>
                <div class="form-group-custom">
                    <label>License Expiration Date*</label>
                    <input type="date" id="driver-license-expiry" class="form-control-custom" required>
                </div>
                <div class="form-grid-2">
                    <div class="form-group-custom">
                        <label>Associate Vehicle</label>
                        <select id="driver-cab" class="form-control-custom">
                            ${cabOptions}
                        </select>
                    </div>
                    <div class="form-group-custom">
                        <label>Status</label>
                        <select id="driver-status" class="form-control-custom">
                            <option value="Active">Active</option>
                            <option value="On Leave">On Leave</option>
                            <option value="Inactive">Inactive</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Save Driver</button>
            </form>
        `;
        showAdminModal("Add Driver Record", html);
    } catch (err) {
        console.error(err);
    }
}

async function showEditDriverModal(driver) {
    await showAddDriverModal();
    document.getElementById('admin-modal-title').textContent = "Modify Driver Details";
    document.getElementById('form-driver-id').value = driver.id;
    document.getElementById('driver-name').value = driver.name;
    document.getElementById('driver-phone').value = driver.phone;
    document.getElementById('driver-license').value = driver.license_number;
    document.getElementById('driver-license-expiry').value = driver.license_expiry;
    document.getElementById('driver-cab').value = driver.assigned_cab_id ? driver.assigned_cab_id : 'None';
    document.getElementById('driver-status').value = driver.status;
}

async function saveDriver(event) {
    event.preventDefault();
    if (!smtToken) return;

    const driverId = document.getElementById('form-driver-id').value;
    const payload = {
        name: document.getElementById('driver-name').value.trim(),
        phone: document.getElementById('driver-phone').value.trim(),
        license_number: document.getElementById('driver-license').value.trim(),
        license_expiry: document.getElementById('driver-license-expiry').value,
        status: document.getElementById('driver-status').value,
        assigned_cab_id: document.getElementById('driver-cab').value
    };

    const url = driverId ? `/api/admin/drivers/${driverId}` : '/api/admin/drivers';
    const method = driverId ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
            closeAdminModal();
            fetchDrivers();
        } else {
            alert(result.error || "Failed to save driver.");
        }
    } catch (err) {
        console.error("Save Driver Error:", err);
    }
}

async function deleteDriver(driverId) {
    if (!confirm("Are you sure you want to remove this driver from registry?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/drivers/${driverId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchDrivers();
        } else {
            alert("Failed to delete driver.");
        }
    } catch (err) {
        console.error("Delete Driver Error:", err);
    }
}

// --- COMPANIES MANAGEMENT ---
const companyDirectory = new Map();

function setCompanyStatus(message, isError) {
    const status = document.getElementById('companies-status');
    if (!status) return;
    status.textContent = message || '';
    status.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function renderCompanies(companies) {
    const tbody = document.getElementById('companies-table-body');
    companyDirectory.clear();
    tbody.replaceChildren();
    if (!companies.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 5;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-muted)';
        cell.textContent = 'No companies yet. Add a company and choose Bengaluru or Hyderabad.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    companies.forEach((company) => {
        companyDirectory.set(company.id, company);
        const row = document.createElement('tr');
        const name = document.createElement('td');
        const strong = document.createElement('strong');
        strong.textContent = company.name;
        name.appendChild(strong);
        const contact = document.createElement('td');
        [company.contact_person, company.contact_email, company.contact_phone].forEach((part) => {
            if (!part) return;
            const line = document.createElement('div');
            line.textContent = part;
            contact.appendChild(line);
        });
        const address = document.createElement('td');
        address.textContent = company.address || '';
        const cities = document.createElement('td');
        cities.textContent = (company.branches || []).map((branch) => branch.city || branch.code).join(', ');
        const actions = document.createElement('td');
        const details = document.createElement('button');
        details.type = 'button';
        details.className = 'status-select';
        details.style.marginRight = '0.25rem';
        details.textContent = 'Details';
        details.addEventListener('click', () => showCompanyDetails(company.id));
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => showEditCompanyModal(company));
        actions.append(details, edit);
        row.append(name, contact, address, cities, actions);
        tbody.appendChild(row);
    });
}

async function fetchCompanies() {
    if (!smtToken) return;
    const tbody = document.getElementById('companies-table-body');
    const addButton = document.getElementById('companies-add-button');
    const isOwner = staffSession.role === 'od';
    if (addButton) addButton.style.display = isOwner ? '' : 'none';
    setCompanyStatus('Loading companies...');
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading companies...</td></tr>';
    try {
        const res = await fetch('/api/companies', { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 403) {
            setCompanyStatus(body.message || 'Only an owner can manage companies.', true);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Company management is limited to owners.</td></tr>';
            return;
        }
        if (!res.ok || !body.success) {
            setCompanyStatus(body.message || 'Companies could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #ef4444;">Companies could not be loaded.</td></tr>';
            return;
        }
        setCompanyStatus('');
        renderCompanies(body.data || []);
    } catch (err) {
        console.error(err);
        setCompanyStatus('Companies could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #ef4444;">Companies could not be loaded.</td></tr>';
    }
}

function cityChoices(selected) {
    const chosen = new Set(selected || []);
    return ['BLR', 'HYD'].map((code) => {
        const label = code === 'BLR' ? 'Bengaluru' : 'Hyderabad';
        const checked = chosen.has(code) ? 'checked' : '';
        return `<label class="check"><input type="checkbox" class="company-city" value="${code}" ${checked}> ${label}</label>`;
    }).join('');
}

function selectedCities() {
    return Array.from(document.querySelectorAll('.company-city:checked')).map((box) => box.value);
}

function showAddCompanyModal() {
    const html = `
        <form id="company-form" onsubmit="saveCompany(event)">
            <input type="hidden" id="form-company-id" value="">
            <div class="form-group-custom">
                <label>Company name*</label>
                <input type="text" id="company-name" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Contact person</label>
                <input type="text" id="company-contact" class="form-control-custom">
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Contact email</label>
                    <input type="email" id="company-email" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Contact phone</label>
                    <input type="text" id="company-phone" class="form-control-custom">
                </div>
            </div>
            <div class="form-group-custom">
                <label>Address</label>
                <textarea id="company-address" class="form-control-custom"></textarea>
            </div>
            <div class="form-group-custom company-cities">
                <label>Cities*</label>
                <div style="display: flex; gap: 1rem;">${cityChoices([])}</div>
            </div>
            <p id="company-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Save company</button>
        </form>
    `;
    showAdminModal('Add company', html);
}

function showEditCompanyModal(company) {
    showAddCompanyModal();
    document.getElementById('admin-modal-title').textContent = 'Edit company';
    document.getElementById('form-company-id').value = company.id;
    document.getElementById('company-name').value = company.name || '';
    document.getElementById('company-contact').value = company.contact_person || '';
    document.getElementById('company-email').value = company.contact_email || '';
    document.getElementById('company-phone').value = company.contact_phone || '';
    document.getElementById('company-address').value = company.address || '';
    const cities = document.querySelector('.company-cities');
    if (cities) cities.remove();
}

function companyPayload() {
    return {
        name: document.getElementById('company-name').value.trim(),
        contact_person: document.getElementById('company-contact').value.trim(),
        contact_email: document.getElementById('company-email').value.trim(),
        contact_phone: document.getElementById('company-phone').value.trim(),
        address: document.getElementById('company-address').value.trim()
    };
}

async function saveCompany(event) {
    event.preventDefault();
    const error = document.getElementById('company-form-error');
    const companyId = document.getElementById('form-company-id').value;
    const payload = companyPayload();
    if (!payload.name) {
        error.textContent = 'Company name is required.';
        return;
    }
    if (!companyId) {
        payload.branch_codes = selectedCities();
        if (!payload.branch_codes.length) {
            error.textContent = 'Select Bengaluru or Hyderabad.';
            return;
        }
    }
    error.textContent = 'Saving...';
    try {
        const res = await fetch(companyId ? `/api/companies/${companyId}` : '/api/companies', {
            method: companyId ? 'PATCH' : 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The company could not be saved.';
            return;
        }
        closeAdminModal();
        fetchCompanies();
    } catch (err) {
        console.error(err);
        error.textContent = 'The company could not be saved.';
    }
}

async function showCompanyDetails(companyId) {
    const holder = document.createElement('div');
    holder.innerHTML = '<p>Loading company...</p>';
    showAdminModal('Company details', '');
    document.getElementById('admin-modal-body').replaceChildren(holder);
    try {
        const res = await fetch(`/api/companies/${companyId}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            holder.textContent = body.message || 'Company details could not be loaded.';
            return;
        }
        const company = body.data;
        companyDirectory.set(company.id, company);
        holder.replaceChildren();
        const title = document.createElement('h3');
        title.textContent = company.name;
        const contact = document.createElement('p');
        contact.textContent = [company.contact_person, company.contact_email, company.contact_phone, company.address]
            .filter(Boolean)
            .join(' · ') || 'No contact details yet.';
        const note = document.createElement('p');
        note.id = 'company-detail-error';
        note.style.color = '#ef4444';
        const cities = document.createElement('div');
        cities.style.display = 'flex';
        cities.style.gap = '1rem';
        ['BLR', 'HYD'].forEach((code) => {
            const label = document.createElement('label');
            label.className = 'check';
            const box = document.createElement('input');
            box.type = 'checkbox';
            box.checked = (company.branches || []).some((branch) => branch.code === code);
            box.addEventListener('change', () => setCompanyCity(company.id, code, box));
            label.append(box, document.createTextNode(code === 'BLR' ? ' Bengaluru' : ' Hyderabad'));
            cities.appendChild(label);
        });
        holder.append(title, contact, cities, note, clientSection(company.id), driverSection(company.id), vehicleSection(company.id));
        loadCompanyClients(company.id);
        loadCompanyDrivers(company.id);
        loadCompanyVehicles(company.id);
    } catch (err) {
        console.error(err);
        holder.textContent = 'Company details could not be loaded.';
    }
}

async function setCompanyCity(companyId, code, box) {
    const note = document.getElementById('company-detail-error');
    if (note) note.textContent = 'Saving city...';
    try {
        const res = await fetch(`/api/companies/${companyId}/branches/${code}`, {
            method: box.checked ? 'POST' : 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            box.checked = !box.checked;
            if (note) note.textContent = body.message || 'The city could not be updated.';
            return;
        }
        if (note) note.textContent = '';
        companyDirectory.set(body.data.id, body.data);
        fetchCompanies();
        if (document.getElementById('company-driver-list')) loadCompanyDrivers(body.data.id);
        if (document.getElementById('company-vehicle-list')) loadCompanyVehicles(body.data.id);
    } catch (err) {
        box.checked = !box.checked;
        if (note) note.textContent = 'The city could not be updated.';
    }
}

function clientSection(companyId) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = 'Clients';
    const list = document.createElement('div');
    list.id = 'company-client-list';
    list.textContent = 'Loading clients...';
    const create = document.createElement('form');
    create.addEventListener('submit', (event) => createCompanyClient(event, companyId));
    create.innerHTML = `
        <div class="form-group-custom"><label>Full name*</label><input id="client-name" class="form-control-custom" required></div>
        <div class="form-group-custom"><label>Email*</label><input id="client-email" type="email" class="form-control-custom" required></div>
        <div class="form-group-custom"><label>Phone</label><input id="client-phone" class="form-control-custom"></div>
        <button type="submit" class="btn btn-primary">Create client</button>
    `;
    const link = document.createElement('form');
    link.addEventListener('submit', (event) => linkExistingClient(event, companyId));
    link.innerHTML = `
        <div class="form-group-custom"><label>Existing client email</label><input id="client-link-email" type="email" class="form-control-custom" required></div>
        <button type="submit" class="btn btn-primary">Link client</button>
    `;
    const error = document.createElement('p');
    error.id = 'company-client-error';
    error.style.color = '#ef4444';
    section.append(heading, list, create, link, error);
    return section;
}

function renderCompanyClients(companyId, clients) {
    const list = document.getElementById('company-client-list');
    if (!list) return;
    list.replaceChildren();
    if (!clients.length) {
        list.textContent = 'No clients linked yet.';
        return;
    }
    clients.forEach((client) => {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.gap = '0.75rem';
        row.style.marginBottom = '0.4rem';
        const label = document.createElement('span');
        label.textContent = [client.full_name, client.email, client.phone].filter(Boolean).join(' · ');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'status-select';
        button.textContent = 'Remove link';
        button.addEventListener('click', () => removeCompanyClient(companyId, client.id));
        row.append(label, button);
        list.appendChild(row);
    });
}

async function loadCompanyClients(companyId) {
    const list = document.getElementById('company-client-list');
    try {
        const res = await fetch(`/api/companies/${companyId}/clients`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            if (list) list.textContent = body.message || 'Clients could not be loaded.';
            return;
        }
        renderCompanyClients(companyId, body.data || []);
    } catch (err) {
        console.error(err);
        if (list) list.textContent = 'Clients could not be loaded.';
    }
}

function setClientError(message) {
    const error = document.getElementById('company-client-error');
    if (error) error.textContent = message || '';
}

async function createCompanyClient(event, companyId) {
    event.preventDefault();
    setClientError('Saving client...');
    try {
        const created = await fetch('/api/clients', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                full_name: document.getElementById('client-name').value.trim(),
                email: document.getElementById('client-email').value.trim(),
                phone: document.getElementById('client-phone').value.trim()
            })
        });
        const createdBody = await created.json();
        if (!created.ok || !createdBody.success) {
            setClientError(createdBody.message || 'The client could not be created.');
            return;
        }
        const linked = await fetch(`/api/companies/${companyId}/clients`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: createdBody.data.id })
        });
        const linkedBody = await linked.json();
        if (!linked.ok || !linkedBody.success) {
            setClientError(linkedBody.message || 'The client was created but could not be linked.');
            return;
        }
        event.target.reset();
        setClientError('');
        loadCompanyClients(companyId);
    } catch (err) {
        console.error(err);
        setClientError('The client could not be created.');
    }
}

async function linkExistingClient(event, companyId) {
    event.preventDefault();
    setClientError('Linking client...');
    try {
        const res = await fetch(`/api/companies/${companyId}/clients`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: document.getElementById('client-link-email').value.trim() })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setClientError(body.message || 'The client could not be linked.');
            return;
        }
        event.target.reset();
        setClientError('');
        loadCompanyClients(companyId);
    } catch (err) {
        console.error(err);
        setClientError('The client could not be linked.');
    }
}

async function removeCompanyClient(companyId, clientId) {
    setClientError('Removing link...');
    try {
        const res = await fetch(`/api/companies/${companyId}/clients/${clientId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setClientError(body.message || 'The link could not be removed.');
            return;
        }
        setClientError('');
        loadCompanyClients(companyId);
    } catch (err) {
        console.error(err);
        setClientError('The link could not be removed.');
    }
}

function driverSection(companyId) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = 'Drivers';
    const list = document.createElement('div');
    list.id = 'company-driver-list';
    list.textContent = 'Loading drivers...';
    const form = document.createElement('form');
    form.addEventListener('submit', (event) => linkCompanyDriver(event, companyId));
    const field = document.createElement('div');
    field.className = 'form-group-custom';
    const label = document.createElement('label');
    label.textContent = 'Link an existing driver';
    const choice = document.createElement('select');
    choice.id = 'company-driver-choice';
    choice.className = 'form-control-custom';
    const error = document.createElement('p');
    error.id = 'company-driver-error';
    error.style.color = '#ef4444';
    const button = document.createElement('button');
    button.type = 'submit';
    button.className = 'btn btn-primary';
    button.textContent = 'Link driver';
    field.append(label, choice);
    form.append(field, error, button);
    section.append(heading, list, form);
    return section;
}

function setCompanyDriverError(message) {
    const error = document.getElementById('company-driver-error');
    if (error) error.textContent = message || '';
}

function companySharesDriverCity(company, driver) {
    const cities = new Set((company.branches || []).map((branch) => branch.code));
    return (driver.branches || []).some((branch) => cities.has(branch.code));
}

async function loadCompanyDrivers(companyId) {
    const list = document.getElementById('company-driver-list');
    const choice = document.getElementById('company-driver-choice');
    const company = companyDirectory.get(companyId);
    if (!list || !choice || !company) return;
    list.textContent = 'Loading drivers...';
    try {
        const [linkedRes, directoryRes] = await Promise.all([
            fetch(`/api/companies/${companyId}/drivers`, { credentials: 'same-origin' }),
            fetch('/api/drivers?active=true', { credentials: 'same-origin' })
        ]);
        const linkedBody = await linkedRes.json();
        const directoryBody = await directoryRes.json();
        if (!linkedRes.ok || !linkedBody.success) {
            list.textContent = linkedBody.message || 'Drivers could not be loaded.';
            return;
        }
        renderCompanyDrivers(companyId, linkedBody.data || []);
        choice.replaceChildren();
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Choose a driver';
        choice.appendChild(placeholder);
        const linkedIds = new Set((linkedBody.data || []).map((driver) => driver.id));
        const eligible = (directoryBody.data || []).filter((driver) => (
            driver.active && !linkedIds.has(driver.id) && companySharesDriverCity(company, driver)
        ));
        eligible.forEach((driver) => {
            const option = document.createElement('option');
            option.value = driver.id;
            const city = driver.primary_branch ? (driver.primary_branch.city || driver.primary_branch.code) : '';
            option.textContent = city ? `${driver.display_name} · ${city}` : driver.display_name;
            choice.appendChild(option);
        });
        if (!eligible.length) {
            const empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'No active drivers share a city with this company';
            choice.appendChild(empty);
        }
    } catch (err) {
        console.error(err);
        list.textContent = 'Drivers could not be loaded.';
    }
}

function renderCompanyDrivers(companyId, drivers) {
    const list = document.getElementById('company-driver-list');
    list.replaceChildren();
    if (!drivers.length) {
        list.textContent = 'No drivers linked to this company.';
        return;
    }
    drivers.forEach((driver) => {
        const row = document.createElement('p');
        const city = driver.primary_branch ? (driver.primary_branch.city || driver.primary_branch.code) : '';
        row.textContent = [
            driver.display_name,
            driver.phone,
            city,
            driver.active ? 'Active' : 'Inactive'
        ].filter(Boolean).join(' · ');
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.5rem';
        remove.textContent = 'Remove link';
        remove.addEventListener('click', () => unlinkCompanyDriver(companyId, driver.id, driver.display_name));
        row.appendChild(remove);
        list.appendChild(row);
    });
}

async function linkCompanyDriver(event, companyId) {
    event.preventDefault();
    const choice = document.getElementById('company-driver-choice');
    if (!choice.value) {
        setCompanyDriverError('Choose a driver from the directory.');
        return;
    }
    setCompanyDriverError('Linking driver...');
    try {
        const res = await fetch(`/api/companies/${companyId}/drivers`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ driver_id: choice.value })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyDriverError(body.message || 'The driver could not be linked.');
            return;
        }
        setCompanyDriverError('');
        loadCompanyDrivers(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyDriverError('The driver could not be linked.');
    }
}

async function unlinkCompanyDriver(companyId, driverId, driverName) {
    const label = driverName || 'this driver';
    if (!window.confirm(`Remove ${label} from this company? The driver and the company both stay in their directories.`)) return;
    setCompanyDriverError('Removing link...');
    try {
        const res = await fetch(`/api/companies/${companyId}/drivers/${driverId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyDriverError(body.message || 'The link could not be removed.');
            return;
        }
        setCompanyDriverError('');
        loadCompanyDrivers(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyDriverError('The link could not be removed.');
    }
}

function vehicleSection(companyId) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = 'Vehicles';
    const list = document.createElement('div');
    list.id = 'company-vehicle-list';
    list.textContent = 'Loading vehicles...';
    const form = document.createElement('form');
    form.addEventListener('submit', (event) => linkCompanyVehicle(event, companyId));
    const field = document.createElement('div');
    field.className = 'form-group-custom';
    const label = document.createElement('label');
    label.textContent = 'Link an existing vehicle';
    const choice = document.createElement('select');
    choice.id = 'company-vehicle-choice';
    choice.className = 'form-control-custom';
    const error = document.createElement('p');
    error.id = 'company-vehicle-error';
    error.style.color = '#ef4444';
    const button = document.createElement('button');
    button.type = 'submit';
    button.className = 'btn btn-primary';
    button.textContent = 'Link vehicle';
    field.append(label, choice);
    form.append(field, error, button);
    section.append(heading, list, form);
    return section;
}

function setCompanyVehicleError(message) {
    const error = document.getElementById('company-vehicle-error');
    if (error) error.textContent = message || '';
}

async function loadCompanyVehicles(companyId) {
    const list = document.getElementById('company-vehicle-list');
    const choice = document.getElementById('company-vehicle-choice');
    const company = companyDirectory.get(companyId);
    if (!list || !choice || !company) return;
    list.textContent = 'Loading vehicles...';
    try {
        const [linkedRes, directoryRes] = await Promise.all([
            fetch(`/api/companies/${companyId}/vehicles`, { credentials: 'same-origin' }),
            fetch('/api/vehicles?status=active', { credentials: 'same-origin' })
        ]);
        const linkedBody = await linkedRes.json();
        const directoryBody = await directoryRes.json();
        if (!linkedRes.ok || !linkedBody.success) {
            list.textContent = linkedBody.message || 'Vehicles could not be loaded.';
            return;
        }
        renderCompanyVehicles(companyId, linkedBody.data || []);
        choice.replaceChildren();
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Choose a vehicle';
        choice.appendChild(placeholder);
        const cities = new Set((company.branches || []).map((branch) => branch.code));
        const linkedIds = new Set((linkedBody.data || []).map((vehicle) => vehicle.id));
        const eligible = (directoryBody.data || []).filter((vehicle) => (
            vehicle.status === 'active'
            && vehicle.branch
            && cities.has(vehicle.branch.code)
            && !linkedIds.has(vehicle.id)
        ));
        eligible.forEach((vehicle) => {
            const option = document.createElement('option');
            option.value = vehicle.id;
            const city = vehicle.branch ? (vehicle.branch.city || vehicle.branch.code) : '';
            option.textContent = city ? `${vehicle.registration_number} · ${city}` : vehicle.registration_number;
            choice.appendChild(option);
        });
        if (!eligible.length) {
            const empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'No active vehicles are garaged in this company\'s cities';
            choice.appendChild(empty);
        }
    } catch (err) {
        console.error(err);
        list.textContent = 'Vehicles could not be loaded.';
    }
}

function renderCompanyVehicles(companyId, vehicles) {
    const list = document.getElementById('company-vehicle-list');
    list.replaceChildren();
    if (!vehicles.length) {
        list.textContent = 'No vehicles linked to this company.';
        return;
    }
    vehicles.forEach((vehicle) => {
        const row = document.createElement('p');
        const city = vehicle.branch ? (vehicle.branch.city || vehicle.branch.code) : '';
        row.textContent = [
            vehicle.registration_number,
            vehicle.model,
            city,
            vehicle.status === 'active' ? 'Active' : 'Inactive'
        ].filter(Boolean).join(' · ');
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.5rem';
        remove.textContent = 'Remove link';
        remove.addEventListener('click', () => unlinkCompanyVehicle(companyId, vehicle.id, vehicle.registration_number));
        row.appendChild(remove);
        list.appendChild(row);
    });
}

async function linkCompanyVehicle(event, companyId) {
    event.preventDefault();
    const choice = document.getElementById('company-vehicle-choice');
    if (!choice.value) {
        setCompanyVehicleError('Choose a vehicle from the directory.');
        return;
    }
    setCompanyVehicleError('Linking vehicle...');
    try {
        const res = await fetch(`/api/companies/${companyId}/vehicles`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_id: choice.value })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyVehicleError(body.message || 'The vehicle could not be linked.');
            return;
        }
        setCompanyVehicleError('');
        loadCompanyVehicles(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyVehicleError('The vehicle could not be linked.');
    }
}

async function unlinkCompanyVehicle(companyId, vehicleId, registration) {
    const label = registration || 'this vehicle';
    if (!window.confirm(`Remove ${label} from this company? The vehicle and the company both stay in their directories.`)) return;
    setCompanyVehicleError('Removing link...');
    try {
        const res = await fetch(`/api/companies/${companyId}/vehicles/${vehicleId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyVehicleError(body.message || 'The link could not be removed.');
            return;
        }
        setCompanyVehicleError('');
        loadCompanyVehicles(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyVehicleError('The link could not be removed.');
    }
}


// --- POSTGRESQL DRIVER DIRECTORY ---
function setPgDriverStatus(message, isError) {
    const status = document.getElementById('pg-drivers-status');
    if (!status) return;
    status.textContent = message || '';
    status.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function pgDriverBranchLabel(driver) {
    const branch = driver.primary_branch;
    if (!branch) return '';
    return branch.city || branch.name || branch.code || '';
}

function pgVerificationLabel(status) {
    if (status === 'verified') return 'Verified';
    if (status === 'rejected') return 'Rejected';
    return 'Unverified';
}

function pgDriverActionButton(label, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'status-select';
    button.style.marginRight = '0.25rem';
    button.textContent = label;
    button.addEventListener('click', onClick);
    return button;
}

function renderPgDrivers(drivers) {
    const tbody = document.getElementById('pg-drivers-table-body');
    tbody.replaceChildren();
    if (!drivers.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 7;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-muted)';
        cell.textContent = 'No drivers in this directory yet.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    drivers.forEach((driver) => {
        const row = document.createElement('tr');
        const name = document.createElement('td');
        name.textContent = driver.display_name || '';
        const phone = document.createElement('td');
        phone.textContent = driver.phone || '';
        const licence = document.createElement('td');
        licence.textContent = driver.license_number || '';
        const branch = document.createElement('td');
        branch.textContent = pgDriverBranchLabel(driver);
        const verification = document.createElement('td');
        verification.textContent = pgVerificationLabel(driver.verification_status);
        const active = document.createElement('td');
        active.textContent = driver.active ? 'Active' : 'Inactive';
        const actions = document.createElement('td');
        actions.append(
            pgDriverActionButton('Details', () => showPgDriverDetails(driver.id)),
            pgDriverActionButton('Edit', () => showEditPgDriverModal(driver))
        );
        if (driver.verification_status === 'unverified') {
            actions.append(
                pgDriverActionButton('Approve', () => reviewPgDriver(driver, 'verified')),
                pgDriverActionButton('Reject', () => reviewPgDriver(driver, 'rejected'))
            );
        } else if (driver.verification_status === 'rejected') {
            actions.append(pgDriverActionButton('Resubmit', () => resubmitPgDriver(driver)));
        } else if (driver.verification_status === 'verified') {
            actions.append(pgDriverActionButton(
                driver.active ? 'Suspend' : 'Restore',
                () => changePgDriverActive(driver, !driver.active)
            ));
        }
        row.append(name, phone, licence, branch, verification, active, actions);
        tbody.appendChild(row);
    });
}

async function fetchPgDrivers() {
    if (!smtToken) return;
    const tbody = document.getElementById('pg-drivers-table-body');
    const addButton = document.getElementById('pg-drivers-add-button');
    const isOwner = staffSession.role === 'od';
    if (addButton) addButton.style.display = isOwner ? '' : 'none';
    setPgDriverStatus('Loading drivers...');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading drivers...</td></tr>';
    const params = new URLSearchParams();
    const name = document.getElementById('pg-driver-search').value.trim();
    const branch = document.getElementById('pg-driver-branch').value;
    const active = document.getElementById('pg-driver-active').value;
    if (name) params.set('name', name);
    if (branch) params.set('branch', branch);
    if (active) params.set('active', active);
    const query = params.toString();
    try {
        const res = await fetch(`/api/drivers${query ? `?${query}` : ''}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 403) {
            setPgDriverStatus(body.message || 'Only an owner can manage drivers.', true);
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Driver management is limited to owners.</td></tr>';
            return;
        }
        if (!res.ok || !body.success) {
            setPgDriverStatus(body.message || 'Drivers could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444;">Drivers could not be loaded.</td></tr>';
            return;
        }
        setPgDriverStatus('');
        renderPgDrivers(body.data || []);
    } catch (err) {
        console.error(err);
        setPgDriverStatus('Drivers could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444;">Drivers could not be loaded.</td></tr>';
    }
}

function showAddPgDriverModal() {
    const html = `
        <form id="pg-driver-form" onsubmit="savePgDriver(event)">
            <input type="hidden" id="pg-driver-id" value="">
            <div class="form-group-custom">
                <label>Driver name*</label>
                <input type="text" id="pg-driver-name" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Phone number</label>
                <input type="text" id="pg-driver-phone" class="form-control-custom">
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Licence number</label>
                    <input type="text" id="pg-driver-licence" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Licence expiry</label>
                    <input type="date" id="pg-driver-expiry" class="form-control-custom">
                </div>
            </div>
            <div class="form-group-custom" id="pg-driver-branch-field">
                <label>Primary branch*</label>
                <select id="pg-driver-city" class="form-control-custom" required>
                    <option value="">Choose a city</option>
                    <option value="BLR">Bengaluru</option>
                    <option value="HYD">Hyderabad</option>
                </select>
            </div>
            <p id="pg-driver-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Save driver</button>
        </form>
    `;
    showAdminModal('Add PostgreSQL driver', html);
}

function showEditPgDriverModal(driver) {
    showAddPgDriverModal();
    document.getElementById('admin-modal-title').textContent = 'Edit PostgreSQL driver';
    document.getElementById('pg-driver-id').value = driver.id;
    document.getElementById('pg-driver-name').value = driver.display_name || '';
    document.getElementById('pg-driver-phone').value = driver.phone || '';
    document.getElementById('pg-driver-licence').value = driver.license_number || '';
    document.getElementById('pg-driver-expiry').value = driver.license_expiry || '';
    const branchField = document.getElementById('pg-driver-branch-field');
    branchField.replaceChildren();
    const note = document.createElement('p');
    note.style.color = 'var(--text-secondary)';
    note.textContent = `Primary branch stays ${pgDriverBranchLabel(driver) || 'as assigned'}. Branch changes are not available here.`;
    branchField.appendChild(note);
}

async function savePgDriver(event) {
    event.preventDefault();
    const error = document.getElementById('pg-driver-form-error');
    const driverId = document.getElementById('pg-driver-id').value;
    const payload = {
        display_name: document.getElementById('pg-driver-name').value.trim(),
        phone: document.getElementById('pg-driver-phone').value.trim(),
        license_number: document.getElementById('pg-driver-licence').value.trim(),
        license_expiry: document.getElementById('pg-driver-expiry').value
    };
    if (!driverId) {
        payload.primary_branch_code = document.getElementById('pg-driver-city').value;
    }
    error.textContent = 'Saving driver...';
    try {
        const res = await fetch(driverId ? `/api/drivers/${driverId}` : '/api/drivers', {
            method: driverId ? 'PATCH' : 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The driver could not be saved.';
            return;
        }
        closeAdminModal();
        fetchPgDrivers();
    } catch (err) {
        console.error(err);
        error.textContent = 'The driver could not be saved.';
    }
}

async function showPgDriverDetails(driverId) {
    showAdminModal('PostgreSQL driver', '<p>Loading driver...</p>');
    try {
        const res = await fetch(`/api/drivers/${driverId}`, { credentials: 'same-origin' });
        const body = await res.json();
        const holder = document.createElement('div');
        if (!res.ok || !body.success) {
            holder.textContent = body.message || 'The driver could not be loaded.';
            document.getElementById('admin-modal-body').replaceChildren(holder);
            return;
        }
        const driver = body.data;
        const title = document.createElement('h3');
        title.textContent = driver.display_name || '';
        const lines = document.createElement('p');
        lines.textContent = [
            driver.phone,
            driver.license_number,
            driver.license_expiry ? `Licence expires ${driver.license_expiry}` : '',
            pgVerificationLabel(driver.verification_status),
            driver.active ? 'Active' : 'Inactive'
        ].filter(Boolean).join(' · ');
        const primary = document.createElement('p');
        primary.textContent = `Primary branch: ${pgDriverBranchLabel(driver) || 'Not recorded'}`;
        const extra = document.createElement('p');
        const others = (driver.branches || []).filter((branch) => !branch.primary);
        extra.textContent = others.length
            ? `Additional branches: ${others.map((branch) => branch.city || branch.code).join(', ')}`
            : 'Additional branches: none';
        const reviews = document.createElement('div');
        const reviewTitle = document.createElement('h4');
        reviewTitle.textContent = 'Verification history';
        reviews.appendChild(reviewTitle);
        const reviewItems = driver.verification_events || [];
        if (!reviewItems.length) {
            const empty = document.createElement('p');
            empty.textContent = 'No verification history yet.';
            reviews.appendChild(empty);
        } else {
            reviewItems.forEach((event) => {
                const item = document.createElement('p');
                item.textContent = `${event.event_name}: ${event.reason} (${event.from_status} to ${event.to_status})`;
                reviews.appendChild(item);
            });
        }
        const changes = document.createElement('div');
        const changeTitle = document.createElement('h4');
        changeTitle.textContent = 'Suspension history';
        changes.appendChild(changeTitle);
        const changeItems = driver.active_changes || [];
        if (!changeItems.length) {
            const empty = document.createElement('p');
            empty.textContent = 'No suspension or restoration yet.';
            changes.appendChild(empty);
        } else {
            changeItems.forEach((change) => {
                const item = document.createElement('p');
                const before = change.active_before ? 'active' : 'inactive';
                const after = change.active_after ? 'active' : 'inactive';
                item.textContent = `${before} to ${after}: ${change.reason}`;
                changes.appendChild(item);
            });
        }
        holder.append(title, lines, primary, extra, reviews, changes);
        document.getElementById('admin-modal-title').textContent = 'PostgreSQL driver';
        document.getElementById('admin-modal-body').replaceChildren(holder);
    } catch (err) {
        console.error(err);
        document.getElementById('admin-modal-body').textContent = 'The driver could not be loaded.';
    }
}

async function postPgDriverAction(path, payload, pending) {
    setPgDriverStatus(pending);
    try {
        const res = await fetch(path, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setPgDriverStatus(body.message || 'The driver could not be updated.', true);
            return;
        }
        setPgDriverStatus('');
        fetchPgDrivers();
    } catch (err) {
        console.error(err);
        setPgDriverStatus('The driver could not be updated.', true);
    }
}

async function reviewPgDriver(driver, decision) {
    const verb = decision === 'verified' ? 'Approve' : 'Reject';
    const reason = window.prompt(`${verb} ${driver.display_name || 'this driver'}. Enter the reason.`);
    if (reason === null) return;
    if (!reason.trim()) {
        setPgDriverStatus('A review reason is required.', true);
        return;
    }
    await postPgDriverAction(
        `/api/drivers/${driver.id}/reviews`,
        { decision, reason: reason.trim() },
        `${verb} driver...`
    );
}

async function resubmitPgDriver(driver) {
    const reason = window.prompt(`Resubmit ${driver.display_name || 'this driver'}. Enter the reason.`);
    if (reason === null) return;
    if (!reason.trim()) {
        setPgDriverStatus('A resubmission reason is required.', true);
        return;
    }
    await postPgDriverAction(
        `/api/drivers/${driver.id}/resubmissions`,
        { reason: reason.trim() },
        'Resubmit driver...'
    );
}

async function changePgDriverActive(driver, next) {
    const verb = next ? 'Restore' : 'Suspend';
    const reason = window.prompt(`${verb} ${driver.display_name || 'this driver'}. Enter the reason.`);
    if (reason === null) return;
    if (!reason.trim()) {
        setPgDriverStatus('A reason is required to suspend or restore a driver.', true);
        return;
    }
    await postPgDriverAction(
        `/api/drivers/${driver.id}/active`,
        { active: next, reason: reason.trim() },
        `${verb} driver...`
    );
}

// --- POSTGRESQL VEHICLE DIRECTORY ---
function setPgVehicleStatus(message, isError) {
    const status = document.getElementById('pg-vehicles-status');
    if (!status) return;
    status.textContent = message || '';
    status.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function pgVehicleBranchLabel(vehicle) {
    const branch = vehicle.branch;
    if (!branch) return '';
    return branch.city || branch.name || branch.code || '';
}

function pgVehicleFuelLabel(vehicle) {
    const fuel = vehicle.fuel_type || '';
    if (vehicle.is_ev && fuel.toLowerCase().indexOf('electric') === -1) {
        return fuel ? fuel + ' · Electric' : 'Electric';
    }
    return fuel;
}

function renderPgVehicles(vehicles) {
    const tbody = document.getElementById('pg-vehicles-table-body');
    tbody.replaceChildren();
    if (!vehicles.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 8;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-muted)';
        cell.textContent = 'No vehicles in this directory yet.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    vehicles.forEach((vehicle) => {
        const row = document.createElement('tr');
        const registration = document.createElement('td');
        registration.textContent = vehicle.registration_number || '';
        const model = document.createElement('td');
        model.textContent = vehicle.model || '';
        const fuel = document.createElement('td');
        fuel.textContent = pgVehicleFuelLabel(vehicle);
        const branch = document.createElement('td');
        branch.textContent = pgVehicleBranchLabel(vehicle);
        const driver = document.createElement('td');
        driver.textContent = vehicle.usual_driver ? vehicle.usual_driver.display_name : '';
        const status = document.createElement('td');
        status.textContent = vehicle.status === 'active' ? 'Active' : 'Inactive';
        const documents = document.createElement('td');
        documents.textContent = String(vehicle.document_count || 0);
        const actions = document.createElement('td');
        const details = document.createElement('button');
        details.type = 'button';
        details.className = 'status-select';
        details.style.marginRight = '0.25rem';
        details.textContent = 'Details';
        details.addEventListener('click', () => showPgVehicleDetails(vehicle.id));
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.style.marginRight = '0.25rem';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => showEditPgVehicleModal(vehicle));
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'status-select';
        toggle.textContent = vehicle.status === 'active' ? 'Deactivate' : 'Activate';
        toggle.addEventListener('click', () => togglePgVehicle(vehicle));
        actions.append(details, edit, toggle);
        row.append(registration, model, fuel, branch, driver, status, documents, actions);
        tbody.appendChild(row);
    });
}

async function fetchPgVehicles() {
    if (!smtToken) return;
    const tbody = document.getElementById('pg-vehicles-table-body');
    const addButton = document.getElementById('pg-vehicles-add-button');
    const isOwner = staffSession.role === 'od';
    if (addButton) addButton.style.display = isOwner ? '' : 'none';
    setPgVehicleStatus('Loading vehicles...');
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Loading vehicles...</td></tr>';
    const params = new URLSearchParams();
    const registration = document.getElementById('pg-vehicle-search').value.trim();
    const branch = document.getElementById('pg-vehicle-branch').value;
    const status = document.getElementById('pg-vehicle-status').value;
    if (registration) params.set('registration', registration);
    if (branch) params.set('branch', branch);
    if (status) params.set('status', status);
    const query = params.toString();
    try {
        const res = await fetch(`/api/vehicles${query ? `?${query}` : ''}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 403) {
            setPgVehicleStatus(body.message || 'Only an owner can manage vehicles.', true);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Vehicle management is limited to owners.</td></tr>';
            return;
        }
        if (!res.ok || !body.success) {
            setPgVehicleStatus(body.message || 'Vehicles could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #ef4444;">Vehicles could not be loaded.</td></tr>';
            return;
        }
        setPgVehicleStatus('');
        renderPgVehicles(body.data || []);
    } catch (err) {
        console.error(err);
        setPgVehicleStatus('Vehicles could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #ef4444;">Vehicles could not be loaded.</td></tr>';
    }
}

function pgVehicleFormHtml() {
    return `
        <form id="pg-vehicle-form" onsubmit="savePgVehicle(event)">
            <input type="hidden" id="pg-vehicle-id" value="">
            <div class="form-group-custom">
                <label>Registration number*</label>
                <input type="text" id="pg-vehicle-registration" class="form-control-custom" required>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Make / model</label>
                    <input type="text" id="pg-vehicle-model" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Capacity</label>
                    <input type="number" id="pg-vehicle-capacity" class="form-control-custom" min="1" max="80">
                </div>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Fuel</label>
                    <input type="text" id="pg-vehicle-fuel" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Electric</label>
                    <input type="checkbox" id="pg-vehicle-ev">
                </div>
            </div>
            <div class="form-group-custom">
                <label>Branch*</label>
                <select id="pg-vehicle-city" class="form-control-custom" required>
                    <option value="">Choose a city</option>
                    <option value="BLR">Bengaluru</option>
                    <option value="HYD">Hyderabad</option>
                </select>
            </div>
            <div class="form-group-custom">
                <label>Usual driver</label>
                <select id="pg-vehicle-driver" class="form-control-custom">
                    <option value="">No usual driver</option>
                </select>
            </div>
            <p id="pg-vehicle-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Save vehicle</button>
        </form>
    `;
}

async function fillPgVehicleDrivers(selectedId, selectedName) {
    const select = document.getElementById('pg-vehicle-driver');
    if (!select) return;
    try {
        const res = await fetch('/api/drivers', { credentials: 'same-origin' });
        const body = await res.json();
        select.replaceChildren();
        const none = document.createElement('option');
        none.value = '';
        none.textContent = 'No usual driver';
        select.appendChild(none);
        (body.data || []).forEach((driver) => {
            const option = document.createElement('option');
            option.value = driver.id;
            option.textContent = driver.display_name + (driver.active ? '' : ' (inactive)');
            select.appendChild(option);
        });
        if (selectedId && !select.querySelector(`option[value="${selectedId}"]`)) {
            const current = document.createElement('option');
            current.value = selectedId;
            current.textContent = selectedName || 'Current driver';
            select.appendChild(current);
        }
        select.value = selectedId || '';
    } catch (err) {
        console.error(err);
    }
}

function showAddPgVehicleModal() {
    showAdminModal('Add PostgreSQL vehicle', pgVehicleFormHtml());
    fillPgVehicleDrivers('', '');
}

function showEditPgVehicleModal(vehicle) {
    showAdminModal('Edit PostgreSQL vehicle', pgVehicleFormHtml());
    document.getElementById('pg-vehicle-id').value = vehicle.id;
    document.getElementById('pg-vehicle-registration').value = vehicle.registration_number || '';
    document.getElementById('pg-vehicle-model').value = vehicle.model || '';
    document.getElementById('pg-vehicle-capacity').value = vehicle.capacity == null ? '' : vehicle.capacity;
    document.getElementById('pg-vehicle-fuel').value = vehicle.fuel_type || '';
    document.getElementById('pg-vehicle-ev').checked = !!vehicle.is_ev;
    document.getElementById('pg-vehicle-city').value = vehicle.branch ? vehicle.branch.code : '';
    const usual = vehicle.usual_driver;
    fillPgVehicleDrivers(usual ? usual.id : '', usual ? usual.display_name : '');
}

async function savePgVehicle(event) {
    event.preventDefault();
    const error = document.getElementById('pg-vehicle-form-error');
    const vehicleId = document.getElementById('pg-vehicle-id').value;
    const capacityText = document.getElementById('pg-vehicle-capacity').value.trim();
    let capacity = null;
    if (capacityText) {
        capacity = Number(capacityText);
        if (!Number.isInteger(capacity)) {
            error.textContent = 'Capacity must be a whole number from 1 to 80.';
            return;
        }
    }
    const payload = {
        registration_number: document.getElementById('pg-vehicle-registration').value.trim(),
        model: document.getElementById('pg-vehicle-model').value.trim(),
        capacity: capacity,
        fuel_type: document.getElementById('pg-vehicle-fuel').value.trim(),
        is_ev: document.getElementById('pg-vehicle-ev').checked,
        branch_code: document.getElementById('pg-vehicle-city').value,
        usual_driver_id: document.getElementById('pg-vehicle-driver').value || null
    };
    error.textContent = 'Saving vehicle...';
    try {
        const res = await fetch(vehicleId ? `/api/vehicles/${vehicleId}` : '/api/vehicles', {
            method: vehicleId ? 'PATCH' : 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The vehicle could not be saved.';
            return;
        }
        closeAdminModal();
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
        error.textContent = 'The vehicle could not be saved.';
    }
}

async function togglePgVehicle(vehicle) {
    const next = vehicle.status === 'active' ? 'inactive' : 'active';
    const question = next === 'inactive'
        ? 'Deactivate this vehicle? The record stays in the PostgreSQL directory and is not deleted.'
        : 'Activate this vehicle? The record stays in the PostgreSQL directory.';
    if (!window.confirm(question)) return;
    setPgVehicleStatus(next === 'inactive' ? 'Deactivating vehicle...' : 'Activating vehicle...');
    try {
        const res = await fetch(`/api/vehicles/${vehicle.id}`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: next })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setPgVehicleStatus(body.message || 'The vehicle status could not be changed.', true);
            return;
        }
        setPgVehicleStatus('');
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
        setPgVehicleStatus('The vehicle status could not be changed.', true);
    }
}

function renderPgVehicleDetails(vehicle) {
    const holder = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = vehicle.registration_number || '';
    const lines = document.createElement('p');
    lines.textContent = [
        vehicle.model,
        vehicle.capacity ? `${vehicle.capacity} seats` : '',
        pgVehicleFuelLabel(vehicle),
        vehicle.status === 'active' ? 'Active' : 'Inactive'
    ].filter(Boolean).join(' · ');
    const branch = document.createElement('p');
    branch.textContent = `Branch: ${pgVehicleBranchLabel(vehicle) || 'Not recorded'}`;
    const driver = document.createElement('p');
    driver.textContent = `Usual driver: ${vehicle.usual_driver ? vehicle.usual_driver.display_name : 'None'}`;
    const note = document.createElement('p');
    note.style.color = 'var(--text-secondary)';
    note.textContent = 'Document records store a type, number, and expiry. This directory does not upload files.';
    const list = document.createElement('div');
    (vehicle.documents || []).forEach((documentRow) => {
        const item = document.createElement('p');
        item.textContent = [
            documentRow.doc_type,
            documentRow.doc_number,
            documentRow.expiry_date ? `expires ${documentRow.expiry_date}` : 'no expiry'
        ].join(' · ');
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.style.marginLeft = '0.5rem';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => {
            document.getElementById('pg-document-id').value = documentRow.id;
            document.getElementById('pg-document-type').value = documentRow.doc_type || '';
            document.getElementById('pg-document-number').value = documentRow.doc_number || '';
            document.getElementById('pg-document-expiry').value = documentRow.expiry_date || '';
        });
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.25rem';
        remove.textContent = 'Remove';
        remove.addEventListener('click', () => deletePgVehicleDocument(vehicle.id, documentRow.id));
        item.append(edit, remove);
        list.appendChild(item);
    });
    if (!(vehicle.documents || []).length) {
        const empty = document.createElement('p');
        empty.textContent = 'No documents recorded.';
        list.appendChild(empty);
    }
    const form = document.createElement('form');
    form.id = 'pg-document-form';
    form.addEventListener('submit', (event) => savePgVehicleDocument(event, vehicle.id));
    form.innerHTML = `
        <input type="hidden" id="pg-document-id" value="">
        <div class="form-grid-2">
            <div class="form-group-custom">
                <label>Document type*</label>
                <input type="text" id="pg-document-type" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Document number*</label>
                <input type="text" id="pg-document-number" class="form-control-custom" required>
            </div>
        </div>
        <div class="form-group-custom">
            <label>Expiry</label>
            <input type="date" id="pg-document-expiry" class="form-control-custom">
        </div>
        <p id="pg-document-error" style="color: #ef4444; min-height: 1.2rem;"></p>
        <button type="submit" class="btn btn-primary">Save document</button>
    `;
    holder.append(title, lines, branch, driver, note, list, form);
    document.getElementById('admin-modal-body').replaceChildren(holder);
}

async function showPgVehicleDetails(vehicleId) {
    showAdminModal('PostgreSQL vehicle', '<p>Loading vehicle...</p>');
    try {
        const res = await fetch(`/api/vehicles/${vehicleId}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            const holder = document.createElement('p');
            holder.textContent = body.message || 'The vehicle could not be loaded.';
            document.getElementById('admin-modal-body').replaceChildren(holder);
            return;
        }
        renderPgVehicleDetails(body.data);
    } catch (err) {
        console.error(err);
        const holder = document.createElement('p');
        holder.textContent = 'The vehicle could not be loaded.';
        document.getElementById('admin-modal-body').replaceChildren(holder);
    }
}

async function savePgVehicleDocument(event, vehicleId) {
    event.preventDefault();
    const error = document.getElementById('pg-document-error');
    const documentId = document.getElementById('pg-document-id').value;
    const payload = {
        doc_type: document.getElementById('pg-document-type').value.trim(),
        doc_number: document.getElementById('pg-document-number').value.trim(),
        expiry_date: document.getElementById('pg-document-expiry').value
    };
    error.textContent = 'Saving document...';
    try {
        const res = await fetch(
            documentId ? `/api/vehicles/${vehicleId}/documents/${documentId}` : `/api/vehicles/${vehicleId}/documents`,
            {
                method: documentId ? 'PATCH' : 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }
        );
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The document could not be saved.';
            return;
        }
        renderPgVehicleDetails(body.data);
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
        error.textContent = 'The document could not be saved.';
    }
}

async function deletePgVehicleDocument(vehicleId, documentId) {
    if (!window.confirm('Remove this document record? The vehicle stays in the directory.')) return;
    try {
        const res = await fetch(`/api/vehicles/${vehicleId}/documents/${documentId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            const error = document.getElementById('pg-document-error');
            if (error) error.textContent = body.message || 'The document could not be removed.';
            return;
        }
        renderPgVehicleDetails(body.data);
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
    }
}

// --- TRANSIT ROSTER ASSIGNMENT ---
async function assignCabToCompany(companyId, companyName) {
    if (!smtToken) return;

    try {
        // Fetch all cabs
        const cabsRes = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const cabs = await cabsRes.json();

        // Fetch all drivers
        const driversRes = await fetch('/api/admin/drivers', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const drivers = await driversRes.json();

        let cabOptions = '';
        cabs.forEach(cab => {
            cabOptions += `<option value="${cab.id}">${cab.reg_number} - ${cab.model} (${cab.fuel_type})</option>`;
        });

        let driverOptions = '';
        drivers.forEach(driver => {
            if (driver.status === 'Active') {
                driverOptions += `<option value="${driver.id}">${driver.name} (License Expires: ${driver.license_expiry})</option>`;
            }
        });

        if (cabs.length === 0 || drivers.length === 0) {
            alert("You need at least one vehicle and one active driver registered to create an assignment.");
            return;
        }

        const html = `
            <form id="assignment-form" onsubmit="saveAssignment(event, ${companyId})">
                <p style="margin-bottom: 1.5rem; font-size: 0.85rem; color: var(--text-secondary);">Select the vehicle and driver to assign to contract for <strong>${companyName}</strong>.</p>
                <div class="form-group-custom">
                    <label>Select Fleet Vehicle*</label>
                    <select id="assign-cab-id" class="form-control-custom" required>
                        ${cabOptions}
                    </select>
                </div>
                <div class="form-group-custom">
                    <label>Select Responsible Driver*</label>
                    <select id="assign-driver-id" class="form-control-custom" required>
                        ${driverOptions}
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Link to Contract</button>
            </form>
        `;
        showAdminModal("Create Fleet Assignment", html);
    } catch (err) {
        console.error("Assign Cab error:", err);
    }
}

async function saveAssignment(event, companyId) {
    event.preventDefault();
    if (!smtToken) return;

    const payload = {
        cab_id: document.getElementById('assign-cab-id').value,
        driver_id: document.getElementById('assign-driver-id').value
    };

    try {
        const res = await fetch(`/api/admin/companies/${companyId}/assignments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeAdminModal();
            fetchCompanies();
        } else {
            const result = await res.json();
            alert(result.error || "Failed to link cab and driver.");
        }
    } catch (err) {
        console.error("Save Assignment Error:", err);
    }
}

async function deleteAssignment(assignmentId, companyId) {
    if (!confirm("Dissolve this vehicle assignment contract?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/assignments/${assignmentId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            loadCompanyAssignments(companyId);
        } else {
            alert("Failed to dissolve assignment.");
        }
    } catch (err) {
        console.error("Delete Assignment Error:", err);
    }
}

// --- EV VEHICLES MANAGEMENT & MONITORING ---
async function fetchEvCabs() {
    if (!smtToken) return;
    const tbody = document.getElementById('ev-table-body');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Connecting telemetry...</td></tr>`;

    try {
        const res = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const cabs = await res.json();
        
        tbody.innerHTML = '';
        const evs = cabs.filter(c => c.is_ev === 1);

        if (evs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No electric vehicles (EV) currently in the registry.</td></tr>`;
            return;
        }

        evs.forEach(cab => {
            const tr = document.createElement('tr');
            const soc = cab.charge_status !== null ? cab.charge_status : 0;
            const estRange = cab.range_km !== null ? `${cab.range_km} KM` : 'N/A';
            const batCap = cab.battery_capacity ? cab.battery_capacity : 'N/A';
            
            // Bar coloring
            let socClass = 'soc-high';
            if (soc < 20) socClass = 'soc-low';
            else if (soc < 70) socClass = 'soc-mid';

            tr.innerHTML = `
                <td><strong style="color: var(--text-primary); font-size: 0.95rem;">${cab.reg_number}</strong></td>
                <td>${cab.model}</td>
                <td>${batCap}</td>
                <td>
                    <div class="soc-container">
                        <div class="soc-info">
                            <span>🔋 Charge Level</span>
                            <span>${soc}%</span>
                        </div>
                        <div class="soc-bar-bg">
                            <div class="soc-bar-fill ${socClass}" style="width: ${soc}%;"></div>
                        </div>
                    </div>
                </td>
                <td><strong style="font-family: var(--font-heading); color: var(--primary-light);">${estRange}</strong></td>
                <td>
                    <span class="status-badge ${cab.status === 'Active' ? 'completed' : cab.status === 'Maintenance' ? 'pending' : 'expired'}">${cab.status}</span>
                </td>
                <td>
                    <button class="status-select" onclick='showTelemetryUpdateModal(${JSON.stringify(cab).replace(/'/g, "\\'")})'>⚡ Update SOC</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444;">Error fetching EV telemetry.</td></tr>`;
    }
}

function showTelemetryUpdateModal(cab) {
    const html = `
        <form id="telemetry-form" onsubmit="saveTelemetry(event, ${cab.id})">
            <p style="margin-bottom: 1.5rem; font-size: 0.85rem; color: var(--text-secondary);">Update real-time battery status and est range for <strong>${cab.reg_number} (${cab.model})</strong>.</p>
            <input type="hidden" id="tel-reg" value="${cab.reg_number}">
            <input type="hidden" id="tel-model" value="${cab.model}">
            <input type="hidden" id="tel-capacity" value="${cab.capacity}">
            <input type="hidden" id="tel-fuel" value="${cab.fuel_type}">
            <input type="hidden" id="tel-status" value="${cab.status}">
            <input type="hidden" id="tel-battery" value="${cab.battery_capacity || ''}">
            
            <div class="form-group-custom">
                <label>Current Battery Charge (SOC %)*</label>
                <input type="number" id="tel-charge" class="form-control-custom" min="0" max="100" value="${cab.charge_status !== null ? cab.charge_status : 100}" required>
            </div>
            <div class="form-group-custom">
                <label>Estimated Remaining Range (KM)*</label>
                <input type="number" id="tel-range" class="form-control-custom" min="0" value="${cab.range_km !== null ? cab.range_km : 200}" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Update Telemetry</button>
        </form>
    `;
    showAdminModal("Update EV Telemetry", html);
}

async function saveTelemetry(event, cabId) {
    event.preventDefault();
    if (!smtToken) return;

    const payload = {
        reg_number: document.getElementById('tel-reg').value,
        model: document.getElementById('tel-model').value,
        capacity: document.getElementById('tel-capacity').value,
        fuel_type: document.getElementById('tel-fuel').value,
        status: document.getElementById('tel-status').value,
        is_ev: 1,
        battery_capacity: document.getElementById('tel-battery').value,
        charge_status: document.getElementById('tel-charge').value,
        range_km: document.getElementById('tel-range').value
    };

    try {
        const res = await fetch(`/api/admin/cabs/${cabId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeAdminModal();
            fetchEvCabs();
        } else {
            alert("Failed to update telemetry.");
        }
    } catch (err) {
        console.error("Save Telemetry Error:", err);
    }
}

// --- LIVE OPERATIONS TRACKING & OPTIMIZATION SYSTEM ---

async function fetchLiveTrips() {
    if (!smtToken) return;

    try {
        // Fetch active trips
        const tripsRes = await fetch('/api/admin/trips', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const trips = await tripsRes.json();

        // Fetch active safety alerts
        const alertsRes = await fetch('/api/admin/safety-alerts', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const alerts = await alertsRes.json();

        // Update Overview Metrics Counters
        let activeVehicles = 0;
        let onboardEmployees = 0;
        let activeAlerts = 0;
        let evTrips = 0;
        let evTotalActive = 0;

        trips.forEach(t => {
            if (t.status === 'En Route' || t.status === 'SOS Alert') {
                activeVehicles++;
            }
            if (t.cab_is_ev === 1) {
                evTotalActive++;
            }
            t.passengers.forEach(p => {
                if (p.status === 'Onboard') {
                    onboardEmployees++;
                }
            });
        });

        alerts.forEach(a => {
            if (a.status === 'Active') {
                activeAlerts++;
            }
        });

        // Compute EV fleet utilization ratio
        const evUtilization = evTotalActive > 0 ? Math.round((evTotalActive / activeVehicles) * 100) || 0 : 0;

        document.getElementById('track-stat-active').textContent = activeVehicles;
        document.getElementById('track-stat-onboard').textContent = onboardEmployees;
        document.getElementById('track-stat-alerts').textContent = activeAlerts;
        document.getElementById('track-stat-ev').textContent = evUtilization + '%';

        // Render live dispatch cards
        renderLiveTripCards(trips);

        // Render Safety alerts table
        renderSafetyAlertsTable(alerts);

        // Render active vehicle points on the Bangalore map
        drawLiveVehicles(trips);

    } catch (err) {
        console.error("Error fetching live operations data:", err);
    }
}

function renderLiveTripCards(trips) {
    const container = document.getElementById('live-trips-list');
    container.innerHTML = '';

    if (trips.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 3rem 0; color: var(--text-muted);">
                <span style="font-size: 2rem;">📭</span>
                <p style="margin-top: 0.5rem; font-size: 0.85rem;">No active dispatches. Click "Run Route Optimizer" to cluster quote requests and deploy fleet.</p>
            </div>
        `;
        return;
    }

    trips.forEach(trip => {
        const div = document.createElement('div');
        div.className = `live-trip-card ${trip.status === 'SOS Alert' ? 'sos-active' : ''}`;
        
        let statusBadgeClass = 'pending';
        if (trip.status === 'En Route') statusBadgeClass = 'in-progress';
        if (trip.status === 'Completed') statusBadgeClass = 'completed';
        if (trip.status === 'SOS Alert') statusBadgeClass = 'expired';

        let progressFillClass = '';
        if (trip.status === 'Completed') progressFillClass = 'completed-fill';
        if (trip.status === 'SOS Alert') progressFillClass = 'sos-fill';

        // Construct passenger status pills
        let passengerPills = '';
        trip.passengers.forEach(p => {
            let pillClass = '';
            if (p.status === 'Onboard') pillClass = 'onboard';
            if (p.status === 'Dropped') pillClass = 'dropped';
            passengerPills += `<span class="passenger-pill ${pillClass}">👤 ${p.name} (${p.status})</span>`;
        });

        // SOS or Resolve button
        let actionBtn = '';
        if (trip.status === 'SOS Alert') {
            actionBtn = `<button class="status-select" style="background:#10b981; color:white; border-color:#10b981; padding:0.25rem 0.6rem;" onclick="resolveTripSOS(${trip.id})">Resolve SOS</button>`;
        } else if (trip.status !== 'Completed') {
            actionBtn = `<button class="status-select" style="background:#ef4444; color:white; border-color:#ef4444; padding:0.25rem 0.6rem;" onclick="triggerTripSOS(${trip.id})">Trigger SOS 🚨</button>`;
        }

        div.innerHTML = `
            <div class="live-trip-header">
                <div>
                    <span style="font-size:0.75rem; text-transform:uppercase; font-weight:600; color:var(--text-muted);">Trip ID: #${trip.id}</span>
                    <h4 style="font-size:1.05rem; margin-top:0.15rem; color:var(--primary);">${trip.route_name}</h4>
                </div>
                <span class="status-badge ${statusBadgeClass}">${trip.status}</span>
            </div>
            
            <div class="live-trip-body">
                <div>
                    <strong>🚖 ${trip.cab_reg}</strong> (${trip.cab_model})<br>
                    <span style="font-size:0.75rem;">Driver: ${trip.driver_name}</span>
                </div>
                <div style="text-align:right;">
                    <strong>Speed: ${trip.speed} km/h</strong><br>
                    <span style="font-size:0.75rem;">ETA: ${trip.eta}</span>
                </div>
            </div>

            <div class="live-trip-progress-container">
                <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-secondary); margin-bottom:0.2rem;">
                    <span>Commute progress</span>
                    <span>${Math.round(trip.progress)}%</span>
                </div>
                <div class="live-trip-progress-bar">
                    <div class="live-trip-progress-fill ${progressFillClass}" style="width: ${trip.progress}%;"></div>
                </div>
            </div>

            <div style="border-top:1px solid var(--border-color); padding-top:0.75rem;">
                <div style="font-size:0.75rem; font-weight:600; margin-bottom:0.3rem;">Passengers Roster:</div>
                <div class="passenger-pills-container">
                    ${passengerPills}
                </div>
            </div>

            <div style="display:flex; justify-content:flex-end; margin-top:0.25rem;">
                ${actionBtn}
            </div>
        `;
        container.appendChild(div);
    });
}

function renderSafetyAlertsTable(alerts) {
    const tbody = document.getElementById('safety-alerts-table-body');
    tbody.innerHTML = '';

    const activeAlerts = alerts.filter(a => a.status === 'Active');

    if (activeAlerts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No active safety logs. Fleet operating within parameters.</td>
            </tr>
        `;
        return;
    }

    activeAlerts.forEach(a => {
        const tr = document.createElement('tr');
        tr.className = 'alert-row-active';
        tr.innerHTML = `
            <td style="padding:0.75rem 1rem; font-size:0.8rem; font-weight:600; color:var(--text-primary);">${a.created_at}</td>
            <td style="padding:0.75rem 1rem; font-size:0.8rem;">
                <strong>Trip #${a.trip_id}</strong><br>
                <span style="font-size:0.72rem; color:var(--text-secondary);">${a.route_name}</span>
            </td>
            <td style="padding:0.75rem 1rem;">
                <span class="doc-badge expired">${a.alert_type}</span>
            </td>
            <td style="padding:0.75rem 1rem; font-size:0.8rem; color:#ef4444; font-weight:500;">${a.details}</td>
            <td style="padding:0.75rem 1rem;">
                <button class="btn btn-secondary" style="padding:0.3rem 0.75rem; font-size:0.75rem;" onclick="resolveTripSOS(${a.trip_id})">Resolve & Clear</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function drawLiveVehicles(trips) {
    const group = document.getElementById('map-active-vehicles-group');
    if (!group) return;
    group.innerHTML = '';

    trips.forEach(trip => {
        if (trip.status === 'Completed' || trip.progress >= 100) return;

        // Find path element
        let pathId = '';
        if (trip.route_name.includes('Amazon')) pathId = 'path-route-amazon';
        else if (trip.route_name.includes('TCS')) pathId = 'path-route-tcs';
        else if (trip.route_name.includes('Optum')) pathId = 'path-route-optum';
        else if (trip.route_name.includes('Electronic City') || trip.route_name.includes('Rental') || trip.route_name.includes('Airport')) pathId = 'path-route-ecity';
        else pathId = 'path-route-optum'; // fallback

        const pathEl = document.getElementById(pathId);
        if (!pathEl) return;

        try {
            const pathLength = pathEl.getTotalLength();
            const percent = trip.progress / 100;
            const point = pathEl.getPointAtLength(percent * pathLength);

            // Determine classes
            let dotClass = 'map-vehicle-dot';
            let dotColor = '#f59e0b'; // default ICE amber
            if (trip.cab_is_ev === 1) {
                dotClass += ' ev-vehicle';
                dotColor = '#10b981'; // Green
            }
            if (trip.status === 'SOS Alert') {
                dotClass += ' sos-vehicle';
                dotColor = '#ef4444'; // Red
            }

            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('class', dotClass);
            g.setAttribute('transform', `translate(${point.x}, ${point.y})`);
            g.setAttribute('onclick', `switchTab('tracking');`);

            // Inner circle
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', '0');
            circle.setAttribute('cy', '0');
            circle.setAttribute('r', '8');
            circle.setAttribute('fill', dotColor);
            g.appendChild(circle);

            // Glowing pulse ring
            const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            pulse.setAttribute('cx', '0');
            pulse.setAttribute('cy', '0');
            pulse.setAttribute('r', '14');
            pulse.setAttribute('fill', 'none');
            pulse.setAttribute('stroke', dotColor);
            pulse.setAttribute('stroke-width', '1.5');
            pulse.setAttribute('opacity', '0.6');
            g.appendChild(pulse);

            // Text Label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', '10');
            text.setAttribute('y', '4');
            text.setAttribute('fill', '#ffffff');
            text.setAttribute('font-size', '8');
            text.setAttribute('font-weight', '700');
            text.setAttribute('font-family', 'sans-serif');
            text.textContent = `${trip.cab_reg} (${trip.speed} km/h)`;
            g.appendChild(text);

            group.appendChild(g);

        } catch (e) {
            console.error("Error drawing vehicle path position:", e);
        }
    });
}

async function optimizeAndDispatch() {
    if (!smtToken) return;

    try {
        const res = await fetch('/api/admin/trips/optimize', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const result = await res.json();
        
        if (res.ok) {
            alert(result.message);
            fetchLiveTrips();
        } else {
            alert(result.error || "Route optimization failed.");
        }
    } catch (err) {
        console.error("Route Optimization Dispatch error:", err);
    }
}

async function simulateTripTick() {
    if (!smtToken) return;

    try {
        const res = await fetch('/api/admin/trips/simulate-tick', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const result = await res.json();
        
        if (res.ok) {
            fetchLiveTrips();
            if (result.alerts_generated > 0) {
                console.log(`[ALERT WARNING] Simulation generated ${result.alerts_generated} new alerts!`);
            }
        }
    } catch (err) {
        console.error("Simulate Progress Tick error:", err);
    }
}

async function triggerTripSOS(tripId) {
    if (!confirm("Are you sure you want to broadcast a simulated passenger SOS emergency alert for this vehicle?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/trips/${tripId}/sos`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchLiveTrips();
        }
    } catch (err) {
        console.error("Trigger SOS Error:", err);
    }
}

async function resolveTripSOS(tripId) {
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/trips/${tripId}/resolve-sos`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchLiveTrips();
        }
    } catch (err) {
        console.error("Resolve SOS Error:", err);
    }
}

async function clearSimulationTrips() {
    if (!confirm("This will dissolve all active tracking paths and release associated vehicles. Continue?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch('/api/admin/trips/clear', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchLiveTrips();
        }
    } catch (err) {
        console.error("Reset simulation error:", err);
    }
}
