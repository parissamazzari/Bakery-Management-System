// All calls go through /api/, which nginx reverse-proxies to the backend
// service - see frontend/nginx.conf.
const API_BASE = "/api";

let PRODUCTS = [];

async function loadProducts() {
  const statusEl = document.getElementById("products-status");
  const gridEl = document.getElementById("products-grid");
  statusEl.textContent = "Loading products...";
  statusEl.className = "status";
  try {
    const res = await fetch(`${API_BASE}/products`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    PRODUCTS = await res.json();
    statusEl.textContent = "";
    gridEl.innerHTML = PRODUCTS.map(renderProductCard).join("");
    populateCartSelects();
  } catch (err) {
    statusEl.textContent = `Failed to load products: ${err.message}`;
    statusEl.className = "status err";
  }
}

function renderProductCard(p) {
  return `
    <div class="product-card ${p.in_stock ? "" : "out-of-stock"}">
      <div class="category">${p.category}</div>
      <h3>${p.name}</h3>
      <div class="price">$${Number(p.price).toFixed(2)}</div>
      <div>${p.in_stock ? "In stock" : "Out of stock"}</div>
    </div>`;
}

function populateCartSelects() {
  document.querySelectorAll(".cart-line select").forEach((sel) => {
    sel.innerHTML = PRODUCTS.filter((p) => p.in_stock)
      .map((p) => `<option value="${p.id}">${p.name} ($${Number(p.price).toFixed(2)})</option>`)
      .join("");
  });
}

function addCartLine() {
  const container = document.getElementById("cart-lines");
  const div = document.createElement("div");
  div.className = "cart-line";
  div.innerHTML = `
    <select></select>
    <input type="number" min="1" value="1" class="qty-input" />
    <button type="button" class="remove-line-btn" title="Remove">✕</button>`;
  container.appendChild(div);
  populateCartSelects();
  div.querySelector(".remove-line-btn").addEventListener("click", () => div.remove());
}

async function placeOrder(event) {
  event.preventDefault();
  const resultEl = document.getElementById("order-result");
  const customerName = document.getElementById("customer-name").value.trim();
  const lines = [...document.querySelectorAll(".cart-line")];

  if (lines.length === 0) {
    resultEl.textContent = "Add at least one product to the order.";
    resultEl.className = "status err";
    return;
  }

  const items = lines.map((line) => ({
    product_id: Number(line.querySelector("select").value),
    quantity: Number(line.querySelector(".qty-input").value),
  }));

  try {
    const res = await fetch(`${API_BASE}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_name: customerName, items }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    resultEl.textContent = `Order #${data.id} placed! Status: ${data.status}. Total: $${Number(data.total_amount).toFixed(2)}`;
    resultEl.className = "status ok";
    document.getElementById("order-id-input").value = data.id;
  } catch (err) {
    resultEl.textContent = `Failed to place order: ${err.message}`;
    resultEl.className = "status err";
  }
}

async function checkStatus(event) {
  event.preventDefault();
  const resultEl = document.getElementById("status-result");
  const orderId = document.getElementById("order-id-input").value;
  try {
    const res = await fetch(`${API_BASE}/orders/${orderId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    resultEl.textContent = `Order #${data.id} — status: ${data.status} — total: $${Number(data.total_amount).toFixed(2)}`;
    resultEl.className = "status ok";
  } catch (err) {
    resultEl.textContent = `Failed to fetch order: ${err.message}`;
    resultEl.className = "status err";
  }
}

document.getElementById("add-line-btn").addEventListener("click", addCartLine);
document.getElementById("order-form").addEventListener("submit", placeOrder);
document.getElementById("status-form").addEventListener("submit", checkStatus);

addCartLine();
loadProducts();
