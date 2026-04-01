import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io

# ============================================================
# SETUP
# ============================================================
# IMPORTANT: Put your actual key in Streamlit Secrets, not here!
# Go to Streamlit Cloud > App Settings > Secrets and add:
#   GEMINI_API_KEY = "your-key-here"
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# ============================================================
# PAGE CONFIG & STYLING
# ============================================================
st.set_page_config(
    page_title="Gaia-Glance",
    page_icon="🌍",
    layout="wide"
)

# Custom CSS for better looking cards and colors
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2C5F2D;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
    }
    .green-card {
        background-color: #E8F5E9;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #4CAF50;
        margin-bottom: 10px;
    }
    .red-card {
        background-color: #FFEBEE;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #E53935;
        margin-bottom: 10px;
    }
    .amber-card {
        background-color: #FFF8E1;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #FFB300;
        margin-bottom: 10px;
    }
    .metric-big {
        font-size: 2.5rem;
        font-weight: bold;
    }
    .food-group-yes {
        color: #4CAF50;
        font-weight: bold;
    }
    .food-group-no {
        color: #E53935;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# BLOCK 1: SESSION STATE — This stores all meals for the day
# ============================================================
# session_state survives Streamlit reruns (every click reruns the script)
# Without this, your meal list would be erased every time

if "meals" not in st.session_state:
    st.session_state.meals = []  # list of meal dictionaries

if "processing" not in st.session_state:
    st.session_state.processing = False

# ============================================================
# BLOCK 1: SIDEBAR — Where users add meals
# ============================================================
with st.sidebar:
    st.title("🌍 Gaia-Glance")
    st.caption("Your Daily Food & Carbon Diary")
    st.divider()

    # Team info
    st.markdown("**👥 The Team**")
    st.caption("Sahasra B. • Saahir A. • Thara N. • Piyush G.")
    st.divider()

    # Meal type selector
    meal_type = st.selectbox(
        "🍽️ What meal is this?",
        ["Breakfast", "Lunch", "Snack", "Dinner"]
    )

    # Input method
    input_method = st.radio("How to add food:", ["📷 Take Photo", "📁 Upload Image", "✏️ Type It"])

    # The actual input
    user_image = None
    user_text = None

    if input_method == "📷 Take Photo":
        user_image = st.camera_input("Take a photo of your meal")
    elif input_method == "📁 Upload Image":
        user_image = st.file_uploader("Upload meal photo", type=["jpg", "jpeg", "png"])
    else:
        user_text = st.text_input("Describe your meal", placeholder="e.g. rice, dal, chicken curry")

    # Submit button
    if st.button("➕ Add Meal", use_container_width=True, type="primary"):
        if user_image or user_text:
            st.session_state.processing = True
            st.rerun()
        else:
            st.warning("Please provide a photo or description first!")

    st.divider()

    # Clear day button
    if st.button("🗑️ Clear All Meals", use_container_width=True):
        st.session_state.meals = []
        st.rerun()

    # Meal count
    st.caption(f"📋 Meals logged today: {len(st.session_state.meals)}")


# ============================================================
# BLOCK 2: GEMINI PROCESSING — The brain of the app
# ============================================================
# This is the prompt that makes everything work.
# It tells Gemini to return structured JSON so we can parse it.

ANALYSIS_PROMPT = """
You are a food nutrition and environmental impact analyst.

Analyze the food provided and return ONLY valid JSON (no markdown, no explanation, no code blocks).

Return this exact JSON structure:
{
  "items": [
    {
      "name": "Food Item Name",
      "weight_g": 200,
      "calories": 350,
      "protein_g": 30,
      "carbs_g": 10,
      "fats_g": 20,
      "fiber_g": 2,
      "food_group": "one of: Grains, Protein, Dairy, Fruits, Vegetables, Fats/Oils",
      "carbon_kg": 4.3,
      "swap": {
        "name": "Lower carbon alternative",
        "carbon_kg": 0.8,
        "reason": "One sentence explaining why this swap works nutritionally"
      }
    }
  ],
  "total_calories": 350,
  "total_carbon_kg": 4.3
}

Rules:
- Identify EVERY food item visible (or described)
- Estimate realistic weights in grams
- Use global average carbon footprint data (based on Poore & Nemecek 2018 study)
- For items with carbon_kg above 2.0, provide a swap suggestion from the SAME food group with SIMILAR calories and protein
- For items with carbon_kg below 2.0, set swap to null
- Be accurate with calories and macros
- Return ONLY the JSON, nothing else
"""

def analyze_meal(image=None, text=None):
    """Send meal to Gemini and get structured JSON back"""
    try:
        if image:
            # Convert image to RGB (camera sometimes gives RGBA which breaks the API)
            img = Image.open(image)
            img = img.convert("RGB")
            response = model.generate_content([ANALYSIS_PROMPT, img])
        else:
            response = model.generate_content(f"{ANALYSIS_PROMPT}\n\nFood items: {text}")

        # Clean up the response — sometimes Gemini wraps JSON in ```json ... ```
        result_text = response.text.strip()
        if result_text.startswith("```"):
            # Remove markdown code block wrapping
            result_text = result_text.split("\n", 1)[1]  # remove first line (```json)
            result_text = result_text.rsplit("```", 1)[0]  # remove last ```

        # Parse the JSON
        data = json.loads(result_text)
        return data

    except json.JSONDecodeError:
        st.error("AI returned badly formatted data. Please try again.")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


# Process the meal if submit was clicked
if st.session_state.processing:
    with st.spinner("🔍 Analyzing your meal with AI..."):
        # We need to re-read the inputs since Streamlit reran
        # Use the sidebar variables captured above
        result = None
        if user_image:
            result = analyze_meal(image=user_image)
        elif user_text:
            result = analyze_meal(text=user_text)

        if result:
            # Store the meal in session state
            meal_entry = {
                "type": meal_type,
                "data": result,
                "image": user_image.getvalue() if user_image else None
            }
            st.session_state.meals.append(meal_entry)

    st.session_state.processing = False
    st.rerun()


# ============================================================
# BLOCK 3 & 4 & 5: MAIN DASHBOARD — Everything the user sees
# ============================================================

# Header
st.markdown('<p class="main-header">🌍 Gaia-Glance Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Track your nutrition and environmental impact — one meal at a time</p>', unsafe_allow_html=True)
st.divider()

# If no meals yet, show empty state
if not st.session_state.meals:
    st.markdown("### 👋 Welcome!")
    st.markdown("Add your first meal using the sidebar to get started.")
    st.markdown("Take a photo or type what you ate — we'll handle the rest.")
    st.stop()  # Stop here, don't render the rest

# ---- MEAL TIMELINE (top section) ----
st.markdown("### 🍽️ Today's Meals")
meal_cols = st.columns(min(len(st.session_state.meals), 4))

for i, meal in enumerate(st.session_state.meals):
    col_index = i % 4
    with meal_cols[col_index]:
        # Meal type header
        st.markdown(f"**{meal['type']}**")

        # Show thumbnail if image exists
        if meal["image"]:
            st.image(meal["image"], use_container_width=True)

        # Quick stats
        total_cal = meal["data"].get("total_calories", 0)
        total_carbon = meal["data"].get("total_carbon_kg", 0)
        st.caption(f"🔥 {total_cal} cal  |  🌿 {total_carbon} kg CO₂")

st.divider()

# ---- CALCULATE DAILY TOTALS ----
# Loop through all meals and add everything up
daily_calories = 0
daily_protein = 0
daily_carbs = 0
daily_fats = 0
daily_fiber = 0
daily_carbon = 0
all_items = []        # flat list of every food item
food_groups_found = set()  # which food groups appeared today

for meal in st.session_state.meals:
    data = meal["data"]
    daily_calories += data.get("total_calories", 0)
    daily_carbon += data.get("total_carbon_kg", 0)

    for item in data.get("items", []):
        daily_protein += item.get("protein_g", 0)
        daily_carbs += item.get("carbs_g", 0)
        daily_fats += item.get("fats_g", 0)
        daily_fiber += item.get("fiber_g", 0)
        food_groups_found.add(item.get("food_group", "Unknown"))
        all_items.append(item)

# ---- NUTRITION SUMMARY (middle section) ----
st.markdown("### 📊 Daily Nutrition Summary")
nutr_left, nutr_right = st.columns([3, 2])

with nutr_left:
    # Big calorie number
    st.metric("Total Calories", f"{daily_calories} kcal")

    # Macro breakdown
    st.markdown("**Macronutrient Breakdown**")

    # Protein bar (recommended ~50g)
    protein_pct = min(daily_protein / 50, 1.0)
    st.markdown(f"Protein: **{daily_protein:.0f}g** / 50g")
    st.progress(protein_pct)

    # Carbs bar (recommended ~250g)
    carbs_pct = min(daily_carbs / 250, 1.0)
    st.markdown(f"Carbs: **{daily_carbs:.0f}g** / 250g")
    st.progress(carbs_pct)

    # Fats bar (recommended ~65g)
    fats_pct = min(daily_fats / 65, 1.0)
    st.markdown(f"Fats: **{daily_fats:.0f}g** / 65g")
    st.progress(fats_pct)

    # Fiber bar (recommended ~25g)
    fiber_pct = min(daily_fiber / 25, 1.0)
    st.markdown(f"Fiber: **{daily_fiber:.0f}g** / 25g")
    st.progress(fiber_pct)

with nutr_right:
    # Food group checklist
    st.markdown("**Food Groups Covered Today**")
    all_groups = ["Grains", "Protein", "Dairy", "Fruits", "Vegetables"]

    for group in all_groups:
        if group in food_groups_found:
            st.markdown(f'<p class="food-group-yes">✅ {group}</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p class="food-group-no">❌ {group} — missing!</p>', unsafe_allow_html=True)

    covered = len(food_groups_found.intersection(set(all_groups)))
    st.caption(f"Coverage: {covered}/5 food groups")

st.divider()

# ---- CARBON FOOTPRINT SECTION ----
st.markdown("### 🌿 Daily Carbon Footprint")

# Big carbon number with color coding
carbon_col1, carbon_col2 = st.columns([1, 2])

with carbon_col1:
    st.metric("Total Daily Carbon", f"{daily_carbon:.1f} kg CO₂")

    # Color-coded verdict
    if daily_carbon < 5:
        st.success("🟢 Low carbon day! Great choices.")
    elif daily_carbon < 10:
        st.warning("🟡 Moderate carbon. Room for improvement.")
    else:
        st.error("🔴 High carbon day. Check the swaps below!")

with carbon_col2:
    # Item-by-item breakdown, sorted by carbon (highest first)
    st.markdown("**Breakdown by Item**")
    sorted_items = sorted(all_items, key=lambda x: x.get("carbon_kg", 0), reverse=True)

    for item in sorted_items:
        carbon = item.get("carbon_kg", 0)
        name = item.get("name", "Unknown")

        # Color code each item
        if carbon >= 3:
            card_class = "red-card"
            dot = "🔴"
        elif carbon >= 1:
            card_class = "amber-card"
            dot = "🟡"
        else:
            card_class = "green-card"
            dot = "🟢"

        st.markdown(
            f'<div class="{card_class}">{dot} <strong>{name}</strong> — {carbon} kg CO₂ ({item.get("calories", 0)} cal)</div>',
            unsafe_allow_html=True
        )

st.divider()

# ---- SWAP SUGGESTIONS SECTION ----
# Only show if there are high-carbon items
high_carbon_items = [item for item in all_items if item.get("carbon_kg", 0) >= 2 and item.get("swap")]

if high_carbon_items:
    st.markdown("### 🔄 Smart Swaps")
    st.markdown("These alternatives give you **similar nutrition** with **less carbon**:")

    for item in high_carbon_items:
        swap = item["swap"]
        if swap:
            saved = item["carbon_kg"] - swap.get("carbon_kg", 0)
            pct = (saved / item["carbon_kg"]) * 100 if item["carbon_kg"] > 0 else 0

            with st.expander(f"🔄 Swap {item['name']} → {swap['name']} (save {saved:.1f} kg CO₂)"):
                swap_col1, swap_col2 = st.columns(2)
                with swap_col1:
                    st.markdown(f'<div class="red-card"><strong>Current:</strong> {item["name"]}<br>🌿 {item["carbon_kg"]} kg CO₂<br>🔥 {item.get("calories", 0)} cal</div>', unsafe_allow_html=True)
                with swap_col2:
                    st.markdown(f'<div class="green-card"><strong>Swap to:</strong> {swap["name"]}<br>🌿 {swap.get("carbon_kg", 0)} kg CO₂<br>💚 {pct:.0f}% less carbon</div>', unsafe_allow_html=True)
                st.markdown(f"**Why this works:** {swap.get('reason', 'Similar nutritional profile with lower environmental impact.')}")

    # Calculate potential savings
    total_savings = sum(
        item["carbon_kg"] - item["swap"].get("carbon_kg", 0)
        for item in high_carbon_items if item.get("swap")
    )
    st.info(f"💡 By making all suggested swaps, you could save **{total_savings:.1f} kg CO₂** today — that's like driving {total_savings * 4:.0f} km less in a car!")

st.divider()

# ---- DAILY SUMMARY ----
st.markdown("### 📝 Daily Summary")
st.markdown(
    f"Today you consumed **{daily_calories} calories** across **{len(st.session_state.meals)} meals**, "
    f"covering **{len(food_groups_found.intersection(set(all_groups)))}/5 food groups**. "
    f"Your total carbon footprint is **{daily_carbon:.1f} kg CO₂**."
)

if high_carbon_items:
    st.markdown(
        f"You have **{len(high_carbon_items)} high-carbon item(s)** that could be swapped for greener alternatives."
    )

st.divider()
st.caption("Gaia-Glance | Built with Streamlit & Gemini AI | Carbon data based on global averages")