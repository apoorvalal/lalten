import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

# --- Configuration & Page Setup ---
st.set_page_config(page_title="Milk Stock Optimization", layout="wide")
st.title("Milk Inventory Optimization")

st.markdown("""
    Milk storage/donation as an investment/saving/consumption problem:

    our 2month old consumes roughly 800ml milk per day. My wife produces 1000ml per day. We have 50 bags of frozen milk (300 ml each approx). We are trying to figure out how many bags to donate so that we (1) have enough to feed the baby as she grows until we wean her off (approx 8-10 months in), (2) end up with minimal wasted milk (~transversality condition) / maximize the donation quantity, (3) my wife goes back to work at 6mo in so we expect a decline in milk production to 600ml per day. Lets write out this finite horizon consumption model and solve it as a fermi-problem. Parametrize everything.
    """)

# --- Sidebar Parameters ---
st.sidebar.header("Model Parameters")

# Stock Inputs
st.sidebar.subheader("Current Inventory")
bags_count = st.sidebar.number_input("Frozen Bags", value=50, step=1)
bag_vol = st.sidebar.number_input("Volume per Bag (ml)", value=300, step=10)
initial_stock = bags_count * bag_vol

# Timeline Inputs
st.sidebar.subheader("Timeline (Months)")
age_now = st.sidebar.number_input("Baby Age Now", value=2.0, step=0.5)
age_work = st.sidebar.number_input("Mom Returns to Work", value=6.0, step=0.5)
age_wean = st.sidebar.number_input("Target Weaning Age", value=10.0, step=0.5)

# Flow Inputs
st.sidebar.subheader("Flow Rates (ml/day)")
cons_daily = st.sidebar.number_input("Daily Consumption", value=800, step=50)
prod_current = st.sidebar.number_input("Current Production", value=1000, step=50)
prod_decline = st.sidebar.slider(
    "Production Retention after Work (%)",
    min_value=0.0,
    max_value=1.0,
    value=0.6,
    help="1.0 = No change, 0.6 = Drops to 60%",
)

# Safety
safety_days = st.sidebar.number_input("Safety Buffer (Days)", value=7, step=1)
buffer_vol = safety_days * cons_daily

# --- Logic & Calculation ---

# Time Horizon
months_remaining = age_wean - age_now
days_total = int(months_remaining * 30)
days_until_work = int((age_work - age_now) * 30)

# Prevent negative indexing if already past work date
days_until_work = max(0, days_until_work)

# Vectorized Simulation
t = np.arange(days_total)

# Production Vector
# Where t < days_until_work, production is high. Else, it drops by multiplier.
prod_phase_2 = prod_current * prod_decline
production_vec = np.where(t < days_until_work, prod_current, prod_phase_2)

# Consumption Vector (Constant per model, but extensible)
consumption_vec = np.full_like(t, cons_daily)

# Stock Vector
net_flow = production_vec - consumption_vec
# Cumulative sum represents change from t=0
stock_trajectory = initial_stock + np.cumsum(net_flow)

# Optimization Logic
# We must ensure Min(Stock) >= Buffer.
# The "excess" is the difference between the global minimum of the trajectory and the buffer.
min_projected_stock = np.min(stock_trajectory)
max_donation_ml = min_projected_stock - buffer_vol
max_donation_bags = np.floor(max_donation_ml / bag_vol)

# --- Dashboard Output ---

# Top Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Current Stock", f"{initial_stock / 1000:.1f} L", f"{bags_count} bags")
c2.metric("Projected Minimum (No Donation)", f"{min_projected_stock / 1000:.1f} L")

if max_donation_bags > 0:
    c3.metric(
        "Recommend Donation",
        f"{int(max_donation_bags)} bags",
        f"{max_donation_ml / 1000:.1f} L",
        delta_color="normal",
    )
else:
    c3.metric(
        "Deficit Warning",
        f"{int(max_donation_bags)} bags",
        "Do not donate",
        delta_color="inverse",
    )

# --- Visualization ---

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

# Plot 1: Flows
ax1.plot(t, production_vec, label="Production", color="green", linewidth=2)
ax1.plot(
    t, consumption_vec, label="Consumption", color="red", linestyle="--", linewidth=2
)
ax1.axvline(x=days_until_work, color="gray", linestyle=":", label="Return to Work")
ax1.set_ylabel("Volume (ml/day)")
ax1.set_title("Daily Flows: Production vs Consumption")
ax1.legend(loc="upper right")
ax1.grid(True, alpha=0.3)

# Plot 2: Stock
ax2.plot(t, stock_trajectory, label="Projected Stock", color="blue", linewidth=2)

# Key Levels
ax2.axhline(y=buffer_vol, color="orange", linestyle="--", label="Safety Buffer")
ax2.axhline(
    y=initial_stock, color="black", linestyle=":", alpha=0.5, label="Initial Stock"
)
ax2.axvline(x=days_until_work, color="gray", linestyle=":")

# Fill for deficit
ax2.fill_between(
    t,
    stock_trajectory,
    buffer_vol,
    where=(stock_trajectory < buffer_vol),
    color="red",
    alpha=0.3,
    label="Shortfall",
)

ax2.set_xlabel("Days from Today")
ax2.set_ylabel("Total Stock (ml)")
ax2.set_title("Inventory Trajectory")
ax2.legend(loc="upper right")
ax2.grid(True, alpha=0.3)

st.pyplot(fig)

# --- Text Summary ---
st.markdown("### Analysis")
st.write(f"""
- **Phase 1 (Next {days_until_work} days):** You are net positive, accumulating **{int(sum(net_flow[:days_until_work]))} ml**.
- **Phase 2 (Work to Wean):** Production drops to **{int(prod_phase_2)} ml/day**. You run a net deficit of **{int(prod_phase_2 - cons_daily)} ml/day**.
- **Result:** To maintain a buffer of {int(buffer_vol)} ml ({safety_days} days), you can safely remove **{int(max_donation_bags)} bags** from inventory today.
""")

st.markdown("""
    Let $t$ be the time in days, where $t=0$ is today (baby is 2 months).
    Let $T_{work} \\approx 120$ (4 months from now, wife returns to work).
    Let $T_{wean} \\approx 240$ (8 months from now, baby is 10 months old).

    Define the stock dynamics $S_t$ as:
    $$
    S_{t+1} = S_t + P_t - C_t
    $$

    **Parameters:**

      * **Initial Stock ($S_0$):** $50 \\text{ bags} \\times 300 \\text{ ml} = 15,000 \\text{ ml}$.
      * **Consumption ($C_t$):** Constant $\\approx 800 \\text{ ml/day}$.
      * **Production ($P_t$):**
        $$
        P_t = \\begin{cases}
            1000, & \\text{if } 0 \\le t < T_{work} \\\\
            600,  & \\text{if } T_{work} \\le t \\le T_{wean}
        \end{cases}
        $$

    **Objective:**

    Find maximize donation $D$ at $t=0$ such that $\min(S_t) \ge \\text{Buffer}$ for all $t \in [0, T_{wean}]$.

    -----

    ### The Fermi Solution

    We can break the timeline into two distinct phases of equal duration (4 months each).

    **Phase 1: Accumulation (Months 2–6)**

      * **Duration:** 120 days.
      * **Net Flow:** $1000 \\text{ (prod)} - 800 \\text{ (cons)} = +200 \\text{ ml/day}$.
      * **Total Accumulation:** $120 \\times 200 = +24,000 \\text{ ml}$.

    **Phase 2: Drawdown (Months 6–10)**

      * **Duration:** 120 days.
      * **Net Flow:** $600 \\text{ (prod)} - 800 \\text{ (cons)} = -200 \\text{ ml/day}$.
      * **Total Drawdown:** $120 \\times -200 = -24,000 \\text{ ml}$.

    **The "Perfect Wash"**
    The surplus generated before your wife returns to work exactly offsets the deficit created after she returns.
    $$
    \Delta S_{total} = +24,000 - 24,000 = 0 \\text{ ml}
    $$

    This implies that your **current inventory ($S_0$) is entirely surplus** relative to the operational requirements of the next 8 months, assuming the parameters hold strictly.

    **Output Summary:**

      * **Projected Final Stock:** 15,000 ml (The math holds; you end exactly where you started).
      * **Safety Buffer:** 5,600 ml (\~19 bags).
      * **Safe Donation:** 9,400 ml (\~30 bags).

    """)
