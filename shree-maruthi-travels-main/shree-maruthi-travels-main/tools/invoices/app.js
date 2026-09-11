const COMPANY_DEFAULT = {
  name: "SHREE MARUTHI TRAVELS",
  address:
    "No.374C, 1st Cross, 9th Main, 1st Stage, Gubbalala, Near Pride Apartment, Jayanagar Housing Society Layout, Bangalore-560061",
  gstin: "29BLBPB8570R2ZE",
  pan: "BLBPB8570R",
  state: "Karnataka",
  stateCode: "29",
  sac: "996601",
  phone1: "+91 96119 75999",
  phone2: "+91 95353 63209",
  email: "info@shreemaruthitravels.com",
  web: "www.shreemaruthitravels.com",
  bank: "ICICI BANK",
  accountName: "SHREE MARUTHI TRAVELS",
  accountNo: "777705070125",
  ifsc: "ICIC0004398",
  branchSrt: "BEML LAYOUT, RR NAGAR",
  branchGst: "Rajarajeshwari Nagar, Bengaluru",
};

const PRESETS = {
  blank: { label: "Custom / blank", template: "gst" },
  tcs: {
    label: "TCS (via SRT)",
    template: "srt",
    invoicePrefix: "SMT-SRT",
    billToName: "SRINIVASA ROAD TRANSPORT PVT. LTD.",
    billToAddress:
      "#134 & 135, Karthik Nagar, LRDE Layout, Doddanekundi Post, Bangalore, KARNATAKA - 560 037.",
    billToGstin: "29ABBCS5611A1ZQ",
    billToPan: "29ABBCS5611A",
    billToState: "Karnataka",
    billToStateCode: "29",
    reverseCharge: "Yes",
    cgst: 0,
    sgst: 0,
    igst: 0,
    clientName: "TCS",
    items: [{ description: "TCS", amount: "44832" }],
    subject:
      "Employee Transportation Service Cabs Bill For The Month Of {period} (Enclosed here Travel Bill Details Statement)",
  },
  amazon: {
    label: "Amazon (via SRT)",
    template: "srt",
    invoicePrefix: "SMT-SRT",
    billToName: "SRINIVASA ROAD TRANSPORT PVT. LTD.",
    billToAddress:
      "#134 & 135, Karthik Nagar, LRDE Layout, Doddanekundi Post, Bangalore, KARNATAKA - 560 037.",
    billToGstin: "29ABBCS5611A1ZQ",
    billToPan: "29ABBCS5611A",
    billToState: "Karnataka",
    billToStateCode: "29",
    reverseCharge: "Yes",
    cgst: 0,
    sgst: 0,
    igst: 0,
    clientName: "Amazon",
    items: [{ description: "AMAZON DEVELOPMENT CENTRE INDIA PVT. LTD.", amount: "" }],
    subject:
      "Employee Transportation Service Cabs Bill For The Month Of {period} (Enclosed here Travel Bill Details Statement)",
  },
  tcsvdp: {
    label: "TCS VDP (via SRT)",
    template: "srt",
    invoicePrefix: "SMT-SRT",
    billToName: "SRINIVASA ROAD TRANSPORT PVT. LTD.",
    billToAddress:
      "#134 & 135, Karthik Nagar, LRDE Layout, Doddanekundi Post, Bangalore, KARNATAKA - 560 037.",
    billToGstin: "29ABBCS5611A1ZQ",
    billToPan: "29ABBCS5611A",
    reverseCharge: "Yes",
    cgst: 0,
    sgst: 0,
    clientName: "TCS VDP",
    items: [{ description: "TCS VDP", amount: "64734" }],
    subject:
      "Employee Transportation Service Cabs Bill For The Month Of {period} (Enclosed here Travel Bill Details Statement)",
  },
  google: {
    label: "Google (via Traveltime)",
    template: "gst",
    invoicePrefix: "SMT-TTM",
    billToName: "TRAVELTIME MOBILITY INDIA PRIVATE LIMITED",
    billToAddress:
      "9TH MAIN, 1207/343 & 1207/1/343/1, HSR LAYOUT, 7TH SECTOR, Bengaluru, Bengaluru Urban, Karnataka, 560102",
    billToGstin: "29AACCT4425H1ZA",
    billToPan: "",
    billToState: "Karnataka",
    billToStateCode: "29",
    clientName: "Google",
    cgst: 2.5,
    sgst: 2.5,
    igst: 0,
    reverseCharge: "No",
    items: [{ description: "Cab Hire Charges (Google)", amount: "1093801" }],
  },
  barclays: {
    label: "Barclays (via Traveltime)",
    template: "gst",
    invoicePrefix: "SMT-TTM",
    billToName: "TRAVELTIME MOBILITY INDIA PRIVATE LIMITED",
    billToAddress:
      "9TH MAIN, 1207/343 & 1207/1/343/1, HSR LAYOUT, 7TH SECTOR, Bengaluru, Bengaluru Urban, Karnataka, 560102",
    billToGstin: "29AACCT4425H1ZA",
    billToState: "Karnataka",
    billToStateCode: "29",
    clientName: "Barclays",
    cgst: 2.5,
    sgst: 2.5,
    items: [{ description: "Cab Hire Charges (Barclays)", amount: "401455" }],
  },
  honeywell: {
    label: "Honeywell (via Traveltime)",
    template: "gst",
    invoicePrefix: "SMT-TTM",
    billToName: "TRAVELTIME MOBILITY INDIA PRIVATE LIMITED",
    billToAddress:
      "9TH MAIN, 1207/343 & 1207/1/343/1, HSR LAYOUT, 7TH SECTOR, Bengaluru, Bengaluru Urban, Karnataka, 560102",
    billToGstin: "29AACCT4425H1ZA",
    billToState: "Karnataka",
    billToStateCode: "29",
    clientName: "Honeywell",
    cgst: 2.5,
    sgst: 2.5,
    items: [{ description: "Cab Hire Charges (Honeywell)", amount: "565435" }],
  },
  schaeffler: {
    label: "Schaeffler (via Traveltime)",
    template: "gst",
    invoicePrefix: "SMT-TTM",
    billToName: "TRAVELTIME MOBILITY INDIA PRIVATE LIMITED",
    billToAddress:
      "9TH MAIN, 1207/343 & 1207/1/343/1, HSR LAYOUT, 7TH SECTOR, Bengaluru, Bengaluru Urban, Karnataka, 560102",
    billToGstin: "29AACCT4425H1ZA",
    billToState: "Karnataka",
    billToStateCode: "29",
    clientName: "Schaeffler",
    cgst: 2.5,
    sgst: 2.5,
    igst: 0,
    dateStyle: "short",
    roundOff: true,
    bank: "BANK OF BARODA",
    accountNo: "07640200003590",
    ifsc: "BARB0JAYANA",
    branchGst: "Jayanagar, Bengaluru",
    items: [{ description: "Cab Hire Charges (Schaeffler)", amount: "56129" }],
  },
  iter: {
    label: "ITER Mobility",
    template: "direct",
    invoicePrefix: "SMT-ITER",
    billToName: "ITER Mobility",
    billToAddress:
      "No.3, 3rd Main, Muneshwara Temple Street, Venkategowda Layout, Hebbala, Kempapura, Bangalore-560024",
    billToGstin: "29AACC4093Q1ZS",
    billToState: "Karnataka",
    billToStateCode: "29",
    clientName: "ITER Mobility",
    cgst: 0,
    sgst: 0,
    igst: 0,
    items: [{ description: "On Call Services for the month of {month}", amount: "14753" }],
  },
  sap: {
    label: "SAP (via Berggruen)",
    template: "gst",
    invoicePrefix: "SMT-SAP",
    billToName: "Berggruen Car Rentals Pvt. Ltd.",
    billToAddress:
      "No.16 & 17, 18th Cross, Gajendra Nagar, Anepalya Main Road, Bangalore-560030",
    billToGstin: "29AADCB1335P1ZF",
    billToState: "Karnataka",
    billToStateCode: "29",
    clientName: "SAP",
    cgst: 2.5,
    sgst: 2.5,
    invMonth: "",
    gracePeriod: "0 Days",
    paymentMethod: "Online RTGS/NEFT",
    items: [{ description: "Car hire charges for the month of {month}", amount: "" }],
    notes:
      "1. Kindly issue Cheque / DD in favour of SHREE MARUTHI TRAVELS.\n2. For any clarification please contact Mr. Byre Gowda A S.\n3. GST on Reverse Charges as per Notification 22/2019 where applicable.",
  },
  deneb: {
    label: "Deneb and Pollux",
    template: "deneb",
    invoicePrefix: "SMT-DPTT",
    billToName: "DENEB AND POLLUX TOURS AND TRAVELS Pvt Ltd",
    billToAddress: "",
    billToGstin: "",
    clientName: "Deneb and Pollux",
    cgst: 0,
    sgst: 0,
    igst: 0,
    sac: "9964",
    items: [{ description: "ETS Cab hire charges of Kalyani Magnum for the month of {month}", amount: "17875" }],
  },
};

const ONES = [
  "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
  "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
  "Seventeen", "Eighteen", "Nineteen",
];
const TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];

function twoDigit(n) {
  n = Math.floor(n);
  if (n < 20) return ONES[n];
  const t = Math.floor(n / 10);
  const o = n % 10;
  return `${TENS[t]}${o ? " " + ONES[o] : ""}`.trim();
}

function threeDigit(n) {
  n = Math.floor(n);
  if (!n) return "";
  const h = Math.floor(n / 100);
  const r = n % 100;
  let s = "";
  if (h) s += ONES[h] + " Hundred";
  if (r) s += (s ? " and " : "") + twoDigit(r);
  return s;
}

function amountInWords(value) {
  let n = Math.round(Number(value) || 0);
  if (n === 0) return "Zero Rupees Only";
  const crore = Math.floor(n / 10000000);
  n %= 10000000;
  const lakh = Math.floor(n / 100000);
  n %= 100000;
  const thousand = Math.floor(n / 1000);
  n %= 1000;
  const parts = [];
  if (crore) parts.push(threeDigit(crore) + " Crore");
  if (lakh) parts.push(twoDigit(lakh) + " Lakh");
  if (thousand) parts.push(twoDigit(thousand) + " Thousand");
  if (n) parts.push(threeDigit(n));
  return parts.join(" ") + " Rupees Only";
}

function inr(n, decimals) {
  const num = Number(n) || 0;
  return num.toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function rupee(n, decimals) {
  return "₹ " + inr(n, decimals);
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function nl(s) {
  return esc(s).replace(/\n/g, "<br>");
}

function $(id) {
  return document.getElementById(id);
}

function company() {
  return {
    name: $("coName").value.trim() || COMPANY_DEFAULT.name,
    address: $("coAddress").value.trim() || COMPANY_DEFAULT.address,
    gstin: $("coGstin").value.trim() || COMPANY_DEFAULT.gstin,
    pan: $("coPan").value.trim() || COMPANY_DEFAULT.pan,
    state: $("coState").value.trim() || COMPANY_DEFAULT.state,
    stateCode: $("coStateCode").value.trim() || COMPANY_DEFAULT.stateCode,
    sac: $("coSac").value.trim() || COMPANY_DEFAULT.sac,
    phone1: $("coPhone1").value.trim() || COMPANY_DEFAULT.phone1,
    phone2: $("coPhone2").value.trim() || COMPANY_DEFAULT.phone2,
    email: $("coEmail").value.trim() || COMPANY_DEFAULT.email,
    web: $("coWeb").value.trim() || COMPANY_DEFAULT.web,
    bank: $("coBank").value.trim() || COMPANY_DEFAULT.bank,
    accountName: $("coAccountName").value.trim() || COMPANY_DEFAULT.accountName,
    accountNo: $("coAccountNo").value.trim() || COMPANY_DEFAULT.accountNo,
    ifsc: $("coIfsc").value.trim() || COMPANY_DEFAULT.ifsc,
    branchSrt: $("coBranchSrt").value.trim() || COMPANY_DEFAULT.branchSrt,
    branchGst: $("coBranchGst").value.trim() || COMPANY_DEFAULT.branchGst,
  };
}

function periodLabel() {
  const from = $("periodFrom").value;
  const to = $("periodTo").value;
  if (!from || !to) return $("periodText").value.trim();
  const a = new Date(from + "T00:00:00");
  const b = new Date(to + "T00:00:00");
  const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const ord = (d) => {
    const n = d.getDate();
    if (n === 1 || n === 21 || n === 31) return n + "st";
    if (n === 2 || n === 22) return n + "nd";
    if (n === 3 || n === 23) return n + "rd";
    return n + "th";
  };
  if (a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()) {
    return `${ord(a)} To ${ord(b)} ${months[a.getMonth()]} ${a.getFullYear()}`;
  }
  return `${ord(a)} ${months[a.getMonth()]} ${a.getFullYear()} To ${ord(b)} ${months[b.getMonth()]} ${b.getFullYear()}`;
}

function monthLabel() {
  const from = $("periodFrom").value;
  if (!from) return $("periodText").value.trim() || "";
  const a = new Date(from + "T00:00:00");
  const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  return `${months[a.getMonth()]} ${a.getFullYear()}`;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const style = $("dateStyle").value;
  if (style === "short") {
    const yy = String(d.getFullYear()).slice(-2);
    return `${String(d.getDate()).padStart(2, "0")}-${months[d.getMonth()]}-${yy}`;
  }
  if (style === "numeric") {
    return `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
  }
  return `${String(d.getDate()).padStart(2, "0")}-${months[d.getMonth()]}-${d.getFullYear()}`;
}

function items() {
  return [...document.querySelectorAll(".item-row")].map((row) => ({
    description: row.querySelector(".item-desc").value.trim(),
    amount: Number(row.querySelector(".item-amt").value) || 0,
  })).filter((x) => x.description || x.amount);
}

function fillTokens(text) {
  return (text || "")
    .replaceAll("{period}", periodLabel())
    .replaceAll("{month}", monthLabel());
}

function calc() {
  const list = items();
  const sub = list.reduce((s, x) => s + x.amount, 0);
  const cgstP = Number($("cgst").value) || 0;
  const sgstP = Number($("sgst").value) || 0;
  const igstP = Number($("igst").value) || 0;
  const cgst = +(sub * cgstP / 100).toFixed(2);
  const sgst = +(sub * sgstP / 100).toFixed(2);
  const igst = +(sub * igstP / 100).toFixed(2);
  let grand = sub + cgst + sgst + igst;
  let roundOff = 0;
  if ($("roundOff").checked) {
    const rounded = Math.round(grand);
    roundOff = +(rounded - grand).toFixed(2);
    grand = rounded;
  }
  return { list, sub, cgstP, sgstP, igstP, cgst, sgst, igst, roundOff, grand };
}

function headerHtml(co) {
  return `
    <div class="inv-header">
      <img class="swoosh" src="assets/swoosh.svg" alt="">
      <img class="inv-logo" src="assets/logo.png" alt="SMT">
      <div class="inv-brand">
        <div class="co-name"><span class="shree">SHREE</span> <span class="rest">MARUTHI TRAVELS</span></div>
        <div class="rules"></div>
      </div>
      <div class="inv-gstin-top">GSTIN: ${esc(co.gstin)}</div>
    </div>`;
}

function footerHtml(co) {
  return `
    <div class="inv-footer">
      <div class="inv-contacts">
        <div class="contact">
          <span class="icon-circle">☎</span>
          <div>${esc(co.phone1)}<br>${esc(co.phone2)}</div>
        </div>
        <div class="contact">
          <span class="icon-circle">✉</span>
          <div>${esc(co.email)}</div>
        </div>
        <div class="contact">
          <span class="icon-circle">🌐</span>
          <div>${esc(co.web)}</div>
        </div>
      </div>
      <img class="wave" src="assets/footer-wave.svg" alt="">
      <div class="addr-bar">
        <span class="icon-circle">📍</span>
        <span>${esc(co.address)}</span>
      </div>
    </div>`;
}

function stampHtml() {
  if (!$("showStamp").checked) return "";
  return `<img class="stamp" src="assets/stamp.svg" alt="stamp">`;
}

function taxCell(amount, decimals) {
  if (!amount) return "—";
  return rupee(amount, decimals);
}

function renderSrt(d, co, t) {
  const dec = 0;
  const rows = t.list.map((x, i) => `
    <tr>
      <td class="ctr">${i + 1}</td>
      <td>${esc(fillTokens(x.description))}</td>
      <td class="num">${rupee(x.amount, dec)}</td>
      <td class="num">${rupee(x.amount, dec)}</td>
    </tr>`).join("");
  const empty = Math.max(0, 2 - t.list.length);
  const blanks = Array.from({ length: empty }, () => `<tr><td>&nbsp;</td><td></td><td></td><td></td></tr>`).join("");
  const subject = fillTokens($("subject").value);
  return `
    ${headerHtml(co)}
    <div class="inv-body">
      <div class="tax-title">TAX INVOICE</div>
      <div class="meta-right">
        Invoice Date: <b>${esc(fmtDate($("invoiceDate").value))}</b><br>
        Invoice No.: <b>${esc($("invoiceNo").value)}</b>
      </div>
      <div class="fromto">
        <div>
          <div>From,</div>
          <div class="who">${esc(co.name)}</div>
          <div>Address: ${esc(co.address)}</div>
        </div>
        <div>
          <div>To,</div>
          <div class="who">${esc($("billToName").value)}</div>
          <div>${nl($("billToAddress").value)}</div>
        </div>
      </div>
      <div class="ids">
        <div>
          Reverse Charges applicable: ${esc($("reverseCharge").value)}<br>
          GSTIN: ${esc(co.gstin)}<br>
          PAN: ${esc(co.pan)}
        </div>
        <div>
          GSTIN: ${esc($("billToGstin").value)}<br>
          PAN: ${esc($("billToPan").value)}
        </div>
      </div>
      <div class="subject">Sub:- ${esc(subject)}</div>
      <table class="inv-table">
        <colgroup><col style="width:12%"><col style="width:46%"><col style="width:21%"><col style="width:21%"></colgroup>
        <thead>
          <tr><th>Sl. No.</th><th>Service Location</th><th>Hire Amount</th><th>Sub Total</th></tr>
        </thead>
        <tbody>
          ${rows}${blanks}
          <tr><td colspan="3" class="sum-label">Amount</td><td class="num">${rupee(t.sub, dec)}</td></tr>
          <tr><td colspan="3" class="sum-label">CGST ${t.cgstP}%</td><td class="num">${taxCell(t.cgst, dec)}</td></tr>
          <tr><td colspan="3" class="sum-label">SGST ${t.sgstP}%</td><td class="num">${taxCell(t.sgst, dec)}</td></tr>
          <tr class="grand-row"><td colspan="3" class="sum-label">Grand Total</td><td class="num">${rupee(t.grand, dec)}</td></tr>
        </tbody>
      </table>
      <div class="words">(Rupees: ${esc(amountInWords(t.grand))})</div>
      <div class="note">Note: GST paid by service Receiver vide G.O. No.13/2017</div>
      <div>SAC Code: ${esc(co.sac)}</div>
      <div class="bank">
        <h3>Bank Details</h3>
        <div>Bank Name: <b>${esc(co.bank)}</b></div>
        <div>Account No: <b>${esc(co.accountNo)}</b></div>
        <div>IFSC Code: <b>${esc(co.ifsc)}</b></div>
        <div>Branch Address : <b>${esc(co.branchSrt)}</b></div>
      </div>
      <div class="srt-sign">
        <div class="left">
          For,<br>${esc(co.name)}<br><br><br>
          Authorised Signatory
        </div>
        <div class="stamp-wrap">${stampHtml()}</div>
      </div>
    </div>
    ${footerHtml(co)}`;
}

function extraGstFields() {
  const bits = [];
  if ($("invMonth").value.trim()) bits.push(`Inv. Month: <b>${esc($("invMonth").value)}</b>`);
  if ($("gracePeriod").value.trim()) bits.push(`Grace Period: <b>${esc($("gracePeriod").value)}</b>`);
  if ($("paymentMethod").value.trim()) bits.push(`Method of Payment: <b>${esc($("paymentMethod").value)}</b>`);
  return bits.length ? `<div>${bits.join("<br>")}</div>` : "";
}

function renderGst(d, co, t, variant) {
  const dec = 2;
  const periodFrom = $("periodFrom").value;
  const periodTo = $("periodTo").value;
  const period = periodFrom && periodTo
    ? `${fmtNumeric(periodFrom)} to ${fmtNumeric(periodTo)}`
    : $("periodText").value;
  const rows = t.list.map((x, i) => `
    <tr>
      <td class="ctr">${i + 1}</td>
      <td><b>${esc(fillTokens(x.description))}</b></td>
      <td class="num"><b>${rupee(x.amount, dec)}</b></td>
    </tr>`).join("");
  const showGst = t.cgstP || t.sgstP || t.igstP;
  const taxRows = [];
  taxRows.push(`<tr><td></td><td class="sum-label">Total</td><td class="num"><b>${rupee(t.sub, dec)}</b></td></tr>`);
  if (t.cgstP || variant !== "direct") {
    taxRows.push(`<tr><td></td><td class="sum-label">CGST ${t.cgstP}%</td><td class="num"><b>${t.cgst ? rupee(t.cgst, 2) : "—"}</b></td></tr>`);
    taxRows.push(`<tr><td></td><td class="sum-label">SGST/UTGST ${t.sgstP}%</td><td class="num"><b>${t.sgst ? rupee(t.sgst, 2) : "—"}</b></td></tr>`);
  }
  if (t.igstP) {
    taxRows.push(`<tr><td></td><td class="sum-label">IGST ${t.igstP}%</td><td class="num"><b>${rupee(t.igst, 2)}</b></td></tr>`);
  }
  if (t.roundOff) {
    taxRows.push(`<tr><td></td><td class="sum-label">Round Off</td><td class="num"><b>${rupee(t.roundOff, 2)}</b></td></tr>`);
  }
  const billLabel = variant === "direct" ? "Bill To" : "To";
  const notes = $("notes").value.trim();
  return `
    ${headerHtml(co)}
    <div class="inv-body">
      <div class="box">
        <div class="title-row">TAX INVOICE</div>
        <div class="split">
          <div>
            ${variant === "direct" ? `<div class="co">Supplier Name</div>` : ""}
            <div class="co">${esc(co.name)}</div>
            <div>${esc(co.address)}</div>
            <div class="kv">PAN no :- ${esc(co.pan)}</div>
            <div class="kv">GST No.: ${esc(co.gstin)}</div>
            <div class="kv">State of Service: ${esc(co.state)}</div>
            <div class="kv">SAC Code:- ${esc(co.sac)}</div>
            <div class="kv">State Code:- ${esc(co.stateCode)}</div>
          </div>
          <div>
            <div class="kv">Invoice No. &nbsp; <b>${esc($("invoiceNo").value)}</b></div>
            <div class="kv">Date &nbsp; <b>${esc(fmtDate($("invoiceDate").value))}</b></div>
            ${extraGstFields()}
          </div>
        </div>
        <div class="split hr">
          <div>
            <div class="co">${billLabel}</div>
            <div class="co">${esc($("billToName").value)}</div>
            <div>${nl($("billToAddress").value)}</div>
            <div class="kv">GSTIN/UIN: ${esc($("billToGstin").value)}</div>
            <div class="kv">State Name : ${esc($("billToState").value)}, Code : ${esc($("billToStateCode").value)}</div>
          </div>
          <div>
            <div class="kv">Service period &nbsp; <b>${esc(period)}</b></div>
            <div class="kv">Client Name &nbsp; <b>${esc($("clientName").value)}</b></div>
            <div class="kv">HSN/SAC &nbsp; <b>${esc(co.sac)}</b></div>
          </div>
        </div>
        <table class="inv-table gst-table">
          <colgroup><col style="width:12%"><col style="width:63%"><col style="width:25%"></colgroup>
          <thead>
            <tr><th>Sl. No.</th><th>Description of services</th><th>Amount</th></tr>
          </thead>
          <tbody>
            ${rows}
            ${showGst || variant !== "direct" ? taxRows.join("") : ""}
            <tr class="grand-row"><td></td><td class="sum-label">Grand Total</td><td class="num">${rupee(t.grand, dec)}</td></tr>
          </tbody>
        </table>
        <div style="padding:5px 7px">
          <div>Amount Chargeable (in words)</div>
          <b>${esc(amountInWords(t.grand))}</b>
        </div>
        ${notes ? `<div class="decl hr">${nl(notes)}</div>` : ""}
        <div class="decl hr">
          <u>Declaration</u><br>
          We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.
        </div>
      </div>
      <div class="gst-bottom">
        <div class="acct">
          <h3>Account Details</h3>
          <div>Account Holder Name: <b>${esc(co.accountName)}</b></div>
          <div>Bank: <b>${esc(co.bank)}</b></div>
          <div>Account No: <b>${esc(co.accountNo)}</b></div>
          <div>IFSC CODE: <b>${esc(co.ifsc)}</b></div>
          <div>Branch: <b>${esc(co.branchGst)}</b></div>
        </div>
        <div class="sign-block">
          <div>For <b>${esc(co.name)}</b></div>
          ${stampHtml()}
          <div style="margin-top:28mm">Signature</div>
        </div>
      </div>
    </div>
    ${footerHtml(co)}`;
}

function fmtNumeric(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
}

function renderDeneb(d, co, t) {
  const dec = 2;
  const desc = t.list.map((x) => fillTokens(x.description)).join(" / ");
  return `
    ${headerHtml(co)}
    <div class="inv-body">
      <div class="original">*Original for Recipient*</div>
      <div class="box">
        <div class="title-row" style="font-style:italic">*TAX INVOICE*</div>
        <div class="split">
          <div>
            <div class="co">${esc(co.name)}</div>
            <div class="kv">GSTIN: ${esc(co.gstin)}</div>
            <div class="kv">PAN No.: ${esc(co.pan)}</div>
            <div class="kv">HSN/SAC Code: ${esc($("coSac").value || "9964")}</div>
          </div>
          <div>
            <div class="kv">Invoice Date: <b>${esc(fmtDate($("invoiceDate").value))}</b></div>
            <div class="kv">Invoice No.: <b>${esc($("invoiceNo").value)}</b></div>
            <div class="kv">Bank Name: <b>${esc(co.bank)}</b></div>
            <div class="kv">Account No.: <b>${esc(co.accountNo)}</b></div>
            <div class="kv">IFSC Code: <b>${esc(co.ifsc)}</b></div>
          </div>
        </div>
        <div class="hr" style="padding:6px 7px">
          <div style="text-decoration:underline;font-weight:800">Billing Address</div>
          <div class="co">${esc($("billToName").value)}</div>
          <div>${nl($("billToAddress").value)}</div>
          <div>Customer GSTIN: ${esc($("billToGstin").value)}</div>
        </div>
        <div class="motto">*Customer Satisfaction Is Our Moto*</div>
        <table class="inv-table gst-table">
          <colgroup><col style="width:72%"><col style="width:28%"></colgroup>
          <thead><tr><th>Description</th><th>Amount (Rs.)</th></tr></thead>
          <tbody>
            <tr>
              <td>${esc(desc)}</td>
              <td class="num">${rupee(t.sub, dec)}</td>
            </tr>
            <tr><td class="sum-label">Gross Amount Before Tax</td><td class="num">${rupee(t.sub, dec)}</td></tr>
            <tr><td class="sum-label">IGST ${t.igstP || 12}%</td><td class="num">${t.igst ? rupee(t.igst, 2) : "—"}</td></tr>
            <tr><td class="sum-label">Round Off</td><td class="num">${t.roundOff ? rupee(t.roundOff, 2) : "—"}</td></tr>
            <tr class="grand-row">
              <td><b>In Words:</b> ${esc(amountInWords(t.grand))}</td>
              <td class="num">${rupee(t.grand, dec)}</td>
            </tr>
          </tbody>
        </table>
        <div class="split" style="border-top:0">
          <div>
            <i>Note: Incase Of Any Discrepancy In This Bill Please Revert Within Three Days From Date Of Submission.</i>
          </div>
          <div class="sign-block" style="margin:0 auto">
            <div>${esc(co.name)}</div>
            ${stampHtml()}
            <div style="margin-top:26mm">Authorised Sign</div>
          </div>
        </div>
        <div class="grey-note">
          GST on reverse charge basis as applicable under Notification No. 13/2017-Central Tax (Rate) and related notifications. SAC 9964 / 996601.
        </div>
      </div>
    </div>
    ${footerHtml(co)}`;
}

function render() {
  const co = company();
  const t = calc();
  const template = $("template").value;
  let html;
  if (template === "srt") html = renderSrt(null, co, t);
  else if (template === "direct") html = renderGst(null, co, t, "direct");
  else if (template === "deneb") html = renderDeneb(null, co, t);
  else html = renderGst(null, co, t, "gst");
  $("invoice").innerHTML = html;
  $("totSub").textContent = rupee(t.sub, 2);
  $("totCgst").textContent = rupee(t.cgst, 2);
  $("totSgst").textContent = rupee(t.sgst, 2);
  $("totIgst").textContent = rupee(t.igst, 2);
  $("totGrand").textContent = rupee(t.grand, 2);
  $("totWords").textContent = amountInWords(t.grand);
  scalePreview();
  persist();
}

function scalePreview() {
  const wrap = $("previewWrap");
  const pane = document.querySelector(".preview-pane");
  const inv = $("invoice");
  if (!wrap || !pane || !inv) return;
  const avail = pane.clientWidth - 40;
  const scale = Math.min(1, avail / 794);
  wrap.style.transform = `scale(${scale})`;
  wrap.style.width = "210mm";
  wrap.style.marginBottom = `${inv.offsetHeight * scale - inv.offsetHeight}px`;
}

function addItem(desc = "", amt = "") {
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input class="item-desc" placeholder="Description / location" value="${esc(desc)}">
    <input class="item-amt" type="number" min="0" step="0.01" placeholder="0.00" value="${esc(amt)}">
    <button type="button" class="btn danger small" title="Remove">×</button>`;
  row.querySelector("button").onclick = () => { row.remove(); render(); };
  $("items").appendChild(row);
}

function applyPreset(id, keepAmounts = false) {
  const p = PRESETS[id];
  if (!p || id === "blank") return;
  $("template").value = p.template;
  if (p.invoicePrefix) {
    const current = $("invoiceNo").value.trim();
    const m = current.match(/(\d+)\s*$/);
    if (m) $("invoiceNo").value = `${p.invoicePrefix}-${m[1].padStart(3, "0")}`;
    else $("invoiceNo").value = nextNumber(p.invoicePrefix);
  }
  $("billToName").value = p.billToName || "";
  $("billToAddress").value = p.billToAddress || "";
  $("billToGstin").value = p.billToGstin || "";
  $("billToPan").value = p.billToPan || "";
  $("billToState").value = p.billToState || "Karnataka";
  $("billToStateCode").value = p.billToStateCode || "29";
  $("clientName").value = p.clientName || "";
  $("reverseCharge").value = p.reverseCharge || "No";
  $("cgst").value = p.cgst ?? 2.5;
  $("sgst").value = p.sgst ?? 2.5;
  $("igst").value = p.igst ?? 0;
  if (p.sac) $("coSac").value = p.sac;
  if (p.invMonth != null) $("invMonth").value = p.invMonth;
  if (p.gracePeriod) $("gracePeriod").value = p.gracePeriod;
  if (p.paymentMethod) $("paymentMethod").value = p.paymentMethod;
  if (p.notes) $("notes").value = p.notes;
  if (p.subject) $("subject").value = p.subject;
  if (p.dateStyle) $("dateStyle").value = p.dateStyle;
  if (p.roundOff != null) $("roundOff").checked = !!p.roundOff;
  $("coBank").value = p.bank || COMPANY_DEFAULT.bank;
  $("coAccountNo").value = p.accountNo || COMPANY_DEFAULT.accountNo;
  $("coIfsc").value = p.ifsc || COMPANY_DEFAULT.ifsc;
  $("coBranchGst").value = p.branchGst || COMPANY_DEFAULT.branchGst;
  $("items").innerHTML = "";
  (p.items || [{ description: "", amount: "" }]).forEach((it) => {
    addItem(it.description, keepAmounts ? it.amount : it.amount);
  });
  toggleTemplateFields();
  render();
}

function nextNumber(prefix) {
  const key = "smt-seq-" + prefix;
  const n = Number(localStorage.getItem(key) || 0) + 1;
  localStorage.setItem(key, String(n));
  return `${prefix}-${String(n).padStart(3, "0")}`;
}

function toggleTemplateFields() {
  const t = $("template").value;
  $("srtOnly").style.display = t === "srt" ? "" : "none";
  $("gstExtras").style.display = t === "gst" || t === "direct" ? "" : "none";
}

function persist() {
  const data = {};
  document.querySelectorAll("[data-persist]").forEach((el) => {
    data[el.id] = el.type === "checkbox" ? el.checked : el.value;
  });
  data.items = items();
  localStorage.setItem("smt-invoice-draft", JSON.stringify(data));
}

function restore() {
  const raw = localStorage.getItem("smt-invoice-draft");
  if (!raw) return false;
  try {
    const data = JSON.parse(raw);
    Object.entries(data).forEach(([id, val]) => {
      if (id === "items") return;
      const el = $(id);
      if (!el) return;
      if (el.type === "checkbox") el.checked = !!val;
      else el.value = val;
    });
    $("items").innerHTML = "";
    (data.items || []).forEach((it) => addItem(it.description, it.amount));
    if (!$("items").children.length) addItem("", "");
    return true;
  } catch {
    return false;
  }
}

function fillCompanyDefaults() {
  $("coName").value = COMPANY_DEFAULT.name;
  $("coAddress").value = COMPANY_DEFAULT.address;
  $("coGstin").value = COMPANY_DEFAULT.gstin;
  $("coPan").value = COMPANY_DEFAULT.pan;
  $("coState").value = COMPANY_DEFAULT.state;
  $("coStateCode").value = COMPANY_DEFAULT.stateCode;
  $("coSac").value = COMPANY_DEFAULT.sac;
  $("coPhone1").value = COMPANY_DEFAULT.phone1;
  $("coPhone2").value = COMPANY_DEFAULT.phone2;
  $("coEmail").value = COMPANY_DEFAULT.email;
  $("coWeb").value = COMPANY_DEFAULT.web;
  $("coBank").value = COMPANY_DEFAULT.bank;
  $("coAccountName").value = COMPANY_DEFAULT.accountName;
  $("coAccountNo").value = COMPANY_DEFAULT.accountNo;
  $("coIfsc").value = COMPANY_DEFAULT.ifsc;
  $("coBranchSrt").value = COMPANY_DEFAULT.branchSrt;
  $("coBranchGst").value = COMPANY_DEFAULT.branchGst;
}

function todayIso() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function monthRange(offset = 0) {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() + offset);
  const from = new Date(d.getFullYear(), d.getMonth(), 1);
  const to = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const iso = (x) => x.toISOString().slice(0, 10);
  return { from: iso(from), to: iso(to) };
}

window.addEventListener("DOMContentLoaded", () => {
  Object.entries(PRESETS).forEach(([id, p]) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = p.label;
    $("preset").appendChild(opt);
  });
  fillCompanyDefaults();
  const restored = restore();
  if (!restored) {
    $("invoiceDate").value = todayIso();
    const r = monthRange(-1);
    $("periodFrom").value = r.from;
    $("periodTo").value = r.to;
    $("invoiceNo").value = nextNumber("SMT");
    $("subject").value =
      "Employee Transportation Service Cabs Bill For The Month Of {period} (Enclosed here Travel Bill Details Statement)";
    addItem("Cab Hire Charges", "");
  }
  if (!$("items").children.length) addItem("", "");
  toggleTemplateFields();

  $("preset").addEventListener("change", () => applyPreset($("preset").value));
  $("template").addEventListener("change", () => { toggleTemplateFields(); render(); });
  $("addItem").addEventListener("click", () => { addItem(); render(); });
  $("printBtn").addEventListener("click", () => window.print());
  $("resetBtn").addEventListener("click", () => {
    if (!confirm("Clear this draft and start a new invoice?")) return;
    localStorage.removeItem("smt-invoice-draft");
    location.reload();
  });
  document.querySelector(".form-pane").addEventListener("input", render);
  document.querySelector(".form-pane").addEventListener("change", render);
  window.addEventListener("resize", scalePreview);
  render();
});
