import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# ============================================================
# SETUP
# ============================================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="Gaia-Glance", page_icon="🌍", layout="wide")

st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================
if "meals" not in st.session_state:
    st.session_state.meals = []

# ============================================================
# THE GEMINI PROMPT
# ============================================================
ANALYSIS_PROMPT = """
You are a food nutrition and environmental impact analyst.

Analyze the food provided and return ONLY valid JSON (no markdown, no explanation, no code blocks, no ```).

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
- Identify EVERY food item visible or described
- Estimate realistic weights in grams
- Use global average carbon footprint data
- For items with carbon_kg above 2.0, provide a swap from the SAME food group with SIMILAR calories
- For items with carbon_kg below 2.0, set swap to null
- Return ONLY the JSON, nothing else
"""

def analyze_meal(image=None, text=None):
    """Send meal to Gemini and get structured JSON back"""
    try:
        if image is not None:
            img = Image.open(image)
            img = img.convert("RGB")
            response = model.generate_content([ANALYSIS_PROMPT, img])
        else:
            response = model.generate_content(ANALYSIS_PROMPT + "\n\nFood items: " + text)

        result_text = response.text.strip()
        # Remove markdown code block if Gemini added it
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            result_text = result_text.rsplit("```", 1)[0]

        data = json.loads(result_text)
        return data

    except json.JSONDecodeError:
        st.error("AI returned bad data. Try again.")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("🌍 Gaia-Glance")
    st.caption("Your Daily Food & Carbon Diary")
    st.divider()
    st.markdown("**👥 The Team**")
    st.caption("Sahasra B. • Saahir A. • Thara N. • Piyush G.")
    st.divider()

    meal_type = st.selectbox("🍽️ What meal is this?", ["Breakfast", "Lunch", "Snack", "Dinner"])
    input_method = st.radio("How to add food:", ["📷 Take Photo", "📁 Upload Image", "✏️ Type It"])

    user_image = None
    user_text = None

    if input_method == "📷 Take Photo":
        user_image = st.camera_input("Take a photo of your meal")
    elif input_method == "📁 Upload Image":
        user_image = st.file_uploader("Upload meal photo", type=["jpg", "jpeg", "png"])
    else:
        user_text = st.text_input("Describe your meal", placeholder="e.g. rice, dal, chicken curry")

    add_clicked = st.button("➕ Add Meal", use_container_width=True, type="primary")

    st.divider()
    if st.button("🗑️ Clear All Meals", use_container_width=True):
        st.session_state.meals = []
        st.rerun()

    st.caption(f"📋 Meals logged today: {len(st.session_state.meals)}")

# ============================================================
# PROCESS MEAL WHEN BUTTON IS CLICKED
# ============================================================
if add_clicked:
    if user_image is not None or user_text:
        with st.spinner("🔍 Analyzing your meal with AI..."):
            result = None
            image_bytes = None

            if user_image is not None:
                image_bytes = user_image.getvalue()
                result = analyze_meal(image=user_image)
            else:
                result = analyze_meal(text=user_text)

            if result:
                meal_entry = {
                    "type": meal_type,
                    "data": result,
                    "image": image_bytes
                }
                st.session_state.meals.append(meal_entry)
                st.rerun()
    else:
        st.warning("Please provide a photo or description first!")

# ============================================================
# MAIN DASHBOARD
# ============================================================
st.markdown("## 🌍 Gaia-Glance Dashboard")
st.markdown("Track your nutrition and environmental impact — one meal at a time")
st.divider()

if not st.session_state.meals:
    st.markdown("### 👋 Welcome!")
    st.markdown("**Add your first meal using the sidebar to get started.**")
    st.markdown("Take a photo or type what you ate — we'll handle the rest.")
    st.stop()

# ---- MEAL TIMELINE ----
st.markdown("### 🍽️ Today's Meals")
num_meals = len(st.session_state.meals)
meal_cols = st.columns(min(num_meals, 4))

for i, meal in enumerate(st.session_state.meals):
    with meal_cols[i % 4]:
        st.markdown(f"**{meal['type']}**")
        if meal["image"]:
            st.image(meal["image"], use_container_width=True)
        total_cal = meal["data"].get("total_calories", 0)
        total_carb = meal["data"].get("total_carbon_kg", 0)
        st.caption(f"🔥 {total_cal} cal  |  🌿 {total_carb} kg CO₂")

st.divider()

# ---- CALCULATE DAILY TOTALS ----
daily_calories = 0
daily_protein = 0
daily_carbs = 0
daily_fats = 0
daily_fiber = 0
daily_carbon = 0
all_items = []
food_groups_found = set()

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

# ---- NUTRITION SUMMARY ----
st.markdown("### 📊 Daily Nutrition Summary")
nutr_left, nutr_right = st.columns([3, 2])

with nutr_left:
    st.metric("Total Calories", f"{daily_calories} kcal")
    st.markdown("**Macronutrient Breakdown**")

    st.markdown(f"Protein: **{daily_protein:.0f}g** / 50g")
    st.progress(min(daily_protein / 50, 1.0))

    st.markdown(f"Carbs: **{daily_carbs:.0f}g** / 250g")
    st.progress(min(daily_carbs / 250, 1.0))

    st.markdown(f"Fats: **{daily_fats:.0f}g** / 65g")
    st.progress(min(daily_fats / 65, 1.0))

    st.markdown(f"Fiber: **{daily_fiber:.0f}g** / 25g")
    st.progress(min(daily_fiber / 25, 1.0))

with nutr_right:
    st.markdown("**Food Groups Covered Today**")
    all_groups = ["Grains", "Protein", "Dairy", "Fruits", "Vegetables"]
    for group in all_groups:
        if group in food_groups_found:
            st.markdown(f"✅ **{group}**")
        else:
            st.markdown(f"❌ {group} — missing!")
    covered = len(food_groups_found.intersection(set(all_groups)))
    st.caption(f"Coverage: {covered}/5 food groups")

st.divider()

# ---- CARBON FOOTPRINT ----
st.markdown("### 🌿 Daily Carbon Footprint")
carbon_col1, carbon_col2 = st.columns([1, 2])

with carbon_col1:
    st.metric("Total Daily Carbon", f"{daily_carbon:.1f} kg CO₂")
    if daily_carbon < 5:
        st.success("🟢 Low carbon day!")
    elif daily_carbon < 10:
        st.warning("🟡 Moderate. Room to improve.")
    else:
        st.error("🔴 High carbon day!")

with carbon_col2:
    st.markdown("**Breakdown by Item**")
    sorted_items = sorted(all_items, key=lambda x: x.get("carbon_kg", 0), reverse=True)
    for item in sorted_items:
        carbon = item.get("carbon_kg", 0)
        name = item.get("name", "Unknown")
        cal = item.get("calories", 0)
        if carbon >= 3:
            card_class = "red-card"
            dot = "🔴"
        elif carbon >= 1:
            card_class = "amber-card"
            dot = "🟡"
        else:
            card_class = "green-card"
            dot = "🟢"
        st.markdown(f'<div class="{card_class}">{dot} <strong>{name}</strong> — {carbon} kg CO₂ ({cal} cal)</div>', unsafe_allow_html=True)

st.divider()

# ---- SWAP SUGGESTIONS ----
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
                s1, s2 = st.columns(2)
                with s1:
                    st.markdown(f'<div class="red-card"><strong>Current:</strong> {item["name"]}<br>🌿 {item["carbon_kg"]} kg CO₂<br>🔥 {item.get("calories", 0)} cal</div>', unsafe_allow_html=True)
                with s2:
                    st.markdown(f'<div class="green-card"><strong>Swap to:</strong> {swap["name"]}<br>🌿 {swap.get("carbon_kg", 0)} kg CO₂<br>💚 {pct:.0f}% less carbon</div>', unsafe_allow_html=True)
                st.markdown(f"**Why this works:** {swap.get('reason', 'Similar nutrition with lower environmental impact.')}")

    total_savings = sum(item["carbon_kg"] - item["swap"].get("carbon_kg", 0) for item in high_carbon_items if item.get("swap"))
    st.info(f"💡 By making all swaps, you could save **{total_savings:.1f} kg CO₂** today!")

st.divider()

# ---- DAILY SUMMARY ----
st.markdown("### 📝 Daily Summary")
st.markdown(
    f"Today you consumed **{daily_calories} calories** across **{len(st.session_state.meals)} meals**, "
    f"covering **{len(food_groups_found.intersection(set(all_groups)))}/5 food groups**. "
    f"Your total carbon footprint is **{daily_carbon:.1f} kg CO₂**."
)

st.divider()
st.caption("Gaia-Glance | Built with Streamlit & Gemini AI")