// SMT Supervisor Dashboard - Administrative Engine

let allInquiries = [];
let smtToken = sessionStorage.getItem('smt_token');
let currentCabIdForDocs = null;

// Page Load Authentication Check
window.onload = function() {
    if (smtToken) {
        // Automatically reveal dashboard and load inquiries tab
        document.getElementById('admin-login-overlay').classList.add('hidden');
        document.getElementById('admin-workspace').style.display = 'flex';
        switchTab('inquiries');
    } else {
        document.getElementById('admin-login-overlay').classList.remove('hidden');
        document.getElementById('admin-workspace').style.display = 'none';
        document.getElementById('passcode-input').focus();
    }
};

// --- LOGIN & AUTHENTICATION ---
async function verifyAdminPasscode() {
    const passcode = document.getElementById('passcode-input').value;
    const errorEl = document.getElementById('login-error');

    try {
        const response = await fetch('/api/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ passcode: passcode })
        });

        const result = await response.json();

        if (response.ok && result.authenticated) {
            smtToken = result.token;
            sessionStorage.setItem('smt_token', smtToken);
            errorEl.style.display = 'none';
            document.getElementById('admin-login-overlay').classList.add('hidden');
            document.getElementById('admin-workspace').style.display = 'flex';
            document.getElementById('passcode-input').value = '';
            
            switchTab('inquiries');
        } else {
            errorEl.style.display = 'block';
            errorEl.textContent = result.error || "Verification failed.";
        }
    } catch (err) {
        console.error("Login Error:", err);
        errorEl.style.display = 'block';
        errorEl.textContent = "Unable to connect to login server.";
    }
}

function handleLoginKey(event) {
    if (event.key === 'Enter') {
        verifyAdminPasscode();
    }
}

function adminLogout() {
    sessionStorage.removeItem('smt_token');
    smtToken = null;
    fetch('/api/admin/logout', { method: 'POST' }).finally(() => {
        document.getElementById('admin-login-overlay').classList.remove('hidden');
        document.getElementById('admin-workspace').style.display = 'none';
        document.getElementById('inquiries-table-body').innerHTML = '';
    });
}

// --- TAB SWITCHER ---
function switchTab(tabId) {
    if (!smtToken) return;
    
    // Hide all tab contents
    document.querySelectorAll('.admin-tab-content').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
    });
    // Remove active class from buttons
    document.querySelectorAll('.admin-sidebar-menu button').forEach(el => {
        el.classList.remove('active');
    });
    
    // Show selected tab content
    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }
    
    // Activate sidebar button
    const targetBtn = document.getElementById(`btn-tab-${tabId}`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }
    
    // Fetch data for the active tab
    if (tabId === 'inquiries') {
        fetchDashboardData();
    } else if (tabId === 'cabs') {
        fetchCabs();
    } else if (tabId === 'drivers') {
        fetchDrivers();
    } else if (tabId === 'companies') {
        fetchCompanies();
    } else if (tabId === 'ev') {
        fetchEvCabs();
    } else if (tabId === 'tracking') {
        fetchLiveTrips();
    }
}

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
async function fetchCompanies() {
    if (!smtToken) return;
    const tbody = document.getElementById('companies-table-body');
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Syncing corporate accounts...</td></tr>`;

    try {
        const res = await fetch('/api/admin/companies', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const companies = await res.json();
        
        tbody.innerHTML = '';
        if (companies.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No corporate clients registered. Click 'Add Corporate Client' to start.</td></tr>`;
            return;
        }

        for (const company of companies) {
            const tr = document.createElement('tr');
            
            // Build cell for listing assignments
            const tdAssignments = document.createElement('td');
            tdAssignments.id = `company-assignments-${company.id}`;
            tdAssignments.innerHTML = `<span style="font-size:0.8rem; color:var(--text-muted);">Syncing roster...</span>`;
            
            tr.innerHTML = `
                <td><strong style="color: var(--primary); font-size: 1rem;">${company.name}</strong></td>
                <td>
                    <div style="font-size: 0.85rem; font-weight: 500;">👤 ${company.contact_person}</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">✉️ ${company.contact_email}</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">📞 ${company.contact_phone}</div>
                </td>
                <td style="font-size: 0.82rem; color: var(--text-secondary); max-width: 250px;">${company.address || 'N/A'}</td>
            `;
            
            tr.appendChild(tdAssignments);
            
            // Actions
            const tdActions = document.createElement('td');
            tdActions.innerHTML = `
                <button class="status-select" style="margin-right: 0.25rem;" onclick="assignCabToCompany(${company.id}, '${company.name.replace(/'/g, "\\'")}')">🔗 Assign</button>
                <button class="status-select" style="margin-right: 0.25rem;" onclick='showEditCompanyModal(${JSON.stringify(company).replace(/'/g, "\\'")})'>Edit</button>
                <button class="status-select" style="color: #ef4444;" onclick="deleteCompany(${company.id})">Del</button>
            `;
            tr.appendChild(tdActions);
            
            tbody.appendChild(tr);
            
            // Load this company's assignments
            loadCompanyAssignments(company.id);
        }
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #ef4444;">Error syncing corporate client database.</td></tr>`;
    }
}

async function loadCompanyAssignments(companyId) {
    if (!smtToken) return;
    const td = document.getElementById(`company-assignments-${companyId}`);
    if (!td) return;

    try {
        const res = await fetch(`/api/admin/companies/${companyId}/assignments`, {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const assignments = await res.json();
        
        td.innerHTML = '';
        if (assignments.length === 0) {
            td.innerHTML = `<span style="font-size:0.8rem; color:var(--text-muted); font-style:italic;">No cabs assigned.</span>`;
            return;
        }

        const listDiv = document.createElement('div');
        listDiv.className = 'corporate-assign-list';
        
        assignments.forEach(item => {
            const row = document.createElement('div');
            row.className = 'corporate-assign-item';
            row.innerHTML = `
                <div>
                    <strong>🚖 ${item.cab_reg}</strong> (${item.cab_model})<br>
                    <span style="font-size: 0.72rem; color: var(--text-secondary);">👷 Driver: ${item.driver_name} (${item.driver_phone})</span>
                </div>
                <button class="status-select" style="color: #ef4444; font-size: 0.75rem; padding: 0.1rem 0.35rem;" onclick="deleteAssignment(${item.assignment_id}, ${companyId})">Remove</button>
            `;
            listDiv.appendChild(row);
        });
        td.appendChild(listDiv);
    } catch (err) {
        td.innerHTML = `<span style="font-size:0.8rem; color:#ef4444;">Sync Error</span>`;
    }
}

function showAddCompanyModal() {
    const html = `
        <form id="company-form" onsubmit="saveCompany(event)">
            <input type="hidden" id="form-company-id" value="">
            <div class="form-group-custom">
                <label>Corporate Client Name*</label>
                <input type="text" id="company-name" class="form-control-custom" placeholder="e.g. Amazon Bangalore" required>
            </div>
            <div class="form-group-custom">
                <label>Key Contact Person</label>
                <input type="text" id="company-contact" class="form-control-custom" placeholder="e.g. Priya Nair">
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Contact Email</label>
                    <input type="email" id="company-email" class="form-control-custom" placeholder="e.g. priya.nair@amazon.com">
                </div>
                <div class="form-group-custom">
                    <label>Contact Phone</label>
                    <input type="text" id="company-phone" class="form-control-custom" placeholder="e.g. +91 804100...">
                </div>
            </div>
            <div class="form-group-custom">
                <label>Office Delivery Address</label>
                <textarea id="company-address" class="form-control-custom" placeholder="Full office workspace location..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Save Corporate Client</button>
        </form>
    `;
    showAdminModal("Add Corporate Client", html);
}

function showEditCompanyModal(company) {
    showAddCompanyModal();
    document.getElementById('admin-modal-title').textContent = "Modify Corporate Client";
    document.getElementById('form-company-id').value = company.id;
    document.getElementById('company-name').value = company.name;
    document.getElementById('company-contact').value = company.contact_person || '';
    document.getElementById('company-email').value = company.contact_email || '';
    document.getElementById('company-phone').value = company.contact_phone || '';
    document.getElementById('company-address').value = company.address || '';
}

async function saveCompany(event) {
    event.preventDefault();
    if (!smtToken) return;

    const companyId = document.getElementById('form-company-id').value;
    const payload = {
        name: document.getElementById('company-name').value.trim(),
        contact_person: document.getElementById('company-contact').value.trim(),
        contact_email: document.getElementById('company-email').value.trim(),
        contact_phone: document.getElementById('company-phone').value.trim(),
        address: document.getElementById('company-address').value.trim()
    };

    const url = companyId ? `/api/admin/companies/${companyId}` : '/api/admin/companies';
    const method = companyId ? 'PUT' : 'POST';

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
            fetchCompanies();
        } else {
            alert(result.error || "Failed to save company.");
        }
    } catch (err) {
        console.error("Save Company Error:", err);
    }
}

async function deleteCompany(companyId) {
    if (!confirm("Are you sure you want to remove this corporate client? All active transit assignments will be dissolved.")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/companies/${companyId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchCompanies();
        } else {
            alert("Failed to delete client company.");
        }
    } catch (err) {
        console.error("Delete Company Error:", err);
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
