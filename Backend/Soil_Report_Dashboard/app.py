from flask import Flask, render_template, request, jsonify
import requests
from google import genai
from google.genai import types  # for configuration types
import markdown

app = Flask(__name__)

# Mapping of SoilGrids parameter codes to descriptive names and explanations
PARAM_MAP = {
    "bdod": ("Bulk Density", "Mass of dry soil per unit volume (cg/cm³)"),
    "cec": ("Cation Exchange Capacity", "Soil's ability to hold essential nutrients (mmol(c)/kg)"),
    "cfvo": ("Coarse Fragment Volume", "Volume fraction of coarse fragments in soil (cm³/dm³)"),
    "clay": ("Clay Content", "Amount of clay in the soil (g/kg)"),
    "nitrogen": ("Nitrogen Content", "Soil nitrogen levels (cg/kg)"),
    "ocd": ("Organic Carbon Density", "Organic carbon per unit volume (dg/dm³)"),
    "ocs": ("Organic Carbon Stock", "Organic carbon per unit mass (dg/kg)"),
    "phh2o": ("Soil pH", "Acidity or alkalinity of the soil"),
    "sand": ("Sand Content", "Amount of sand in the soil (g/kg)"),
    "silt": ("Silt Content", "Amount of silt in the soil (g/kg)"),
    "soc": ("Soil Organic Carbon", "Concentration of organic carbon in the soil (dg/kg)"),
    "wv0010": ("Water Content (0-10cm)", "Water content for shallow soil layers (10^-2 cm³/cm³)"),
    "wv0033": ("Water Content (0-33cm)", "Water content for intermediate soil layers (10^-2 cm³/cm³)"),
    "wv1500": ("Water Content (1500mm)", "Water content for deep soil layers (10^-2 cm³/cm³)")
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_soil_report', methods=['POST'])
def get_soil_report():
    data = request.get_json()
    lat = data.get("lat")
    lon = data.get("lon")
    if not lat or not lon:
        return jsonify({"error": "Latitude and Longitude are required"}), 400

    headers = {"accept": "application/json"}
    timeout_val = 10  # seconds

    # Fetch Soil Classification
    classification_url = "https://dev-rest.isric.org/soilgrids/v2.0/classification/query"
    classification_params = {
        "lon": lon,
        "lat": lat,
        "number_classes": "5"
    }
    try:
        class_response = requests.get(classification_url, params=classification_params,
                                      headers=headers, timeout=timeout_val)
        class_response.raise_for_status()
        class_data = class_response.json()
    except Exception as e:
        return jsonify({"error": "Failed to fetch soil classification: " + str(e)}), 500

    soil_classification = {
        "soil_type": class_data.get("wrb_class_name", "Unknown"),
        "soil_probabilities": class_data.get("wrb_class_probability", [])
    }

    # Fetch Soil Properties
    properties_url = "https://dev-rest.isric.org/soilgrids/v2.0/properties/query"
    properties_params = {
        "lon": lon,
        "lat": lat,
        "property": [
            "bdod", "cec", "cfvo", "clay", "nitrogen",
            "ocd", "ocs", "phh2o", "sand", "silt",
            "soc", "wv0010", "wv0033", "wv1500"
        ],
        "depth": "5-15cm",
        "value": "mean"
    }
    try:
        prop_response = requests.get(properties_url, params=properties_params,
                                     headers=headers, timeout=timeout_val)
        prop_response.raise_for_status()
        prop_data = prop_response.json()
    except Exception as e:
        return jsonify({"error": "Failed to fetch soil properties: " + str(e)}), 500

    properties_list = []
    layers = prop_data.get("properties", {}).get("layers", [])
    for layer in layers:
        param_code = layer.get("name")
        readable_name, description = PARAM_MAP.get(param_code, (param_code.upper(), "No description available"))
        # Get the 'mean' value for the first depth entry
        value = layer.get("depths", [{}])[0].get("values", {}).get("mean")
        if value is not None:
            if param_code in ["wv0010", "wv0033", "wv1500"]:
                final_value = value / 10.0
                unit = layer.get("unit_measure", {}).get("target_units", "")
            elif param_code == "phh2o":
                final_value = value / 10.0
                unit = layer.get("unit_measure", {}).get("mapped_units", "").replace("*10", "").strip() or "pH"
            else:
                final_value = value
                unit = layer.get("unit_measure", {}).get("mapped_units", "")
        else:
            final_value = "No Data"
            unit = ""
        properties_list.append({
            "parameter": readable_name,
            "value": final_value,
            "unit": unit,
            "description": description
        })

    # -----------------------------------------------------------
    # Add Estimated Phosphorus (P) and Potassium (K)
    # -----------------------------------------------------------
    # Hardcode Total Phosphorus value to 500 mg/kg (average for the region)
    total_p = 5  # mg/kg

    # Extract necessary parameters for estimation
    pH_value = None
    cec_value = None
    soc_value = None
    clay_value = None

    for prop in properties_list:
        if prop["parameter"] == "Soil pH" and prop["value"] != "No Data":
            try:
                pH_value = float(prop["value"])
            except:
                pH_value = None
        elif prop["parameter"] == "Cation Exchange Capacity" and prop["value"] != "No Data":
            try:
                cec_value = float(prop["value"])
            except:
                cec_value = None
        elif prop["parameter"] == "Soil Organic Carbon" and prop["value"] != "No Data":
            try:
                soc_value = float(prop["value"])
            except:
                soc_value = None
        elif prop["parameter"] == "Clay Content" and prop["value"] != "No Data":
            try:
                clay_value = float(prop["value"])
            except:
                clay_value = None

    # Estimate available phosphorus (P) using an empirical approach
    if pH_value is not None and soc_value is not None and cec_value is not None:
        if pH_value < 7:
            p_value = (0.4 * total_p * soc_value) / (pH_value + 1)
        else:
            p_value = (0.5 * total_p * cec_value) / (pH_value + 1)
        p_value = round(p_value)  # Round to the nearest integer
    else:
        p_value = "No Data"

    # Estimate available potassium (K) using an empirical model
    if cec_value is not None and clay_value is not None and soc_value is not None:
        k_value = (0.1 * cec_value) + (0.02 * clay_value) + (0.005 * soc_value)
        k_value = round(k_value)  # Round to the nearest integer
    else:
        k_value = "No Data"

    # Append the computed P and K values to the properties list.
    properties_list.append({
        "parameter": "Estimated Phosphorus (P)",
        "value": p_value,
        "unit": "cg/kg",
        "description": "Estimated available phosphorus using an empirical model with a hardcoded total P of 500 mg/kg."
    })
    properties_list.append({
        "parameter": "Estimated Potassium (K)",
        "value": k_value,
        "unit": "cg/kg",
        "description": "Estimated available potassium based on an empirical model using CEC, clay content, and SOC."
    })

    soil_report = {
        "classification": soil_classification,
        "properties": properties_list
    }
    return jsonify(soil_report)

@app.route('/analyze_soil', methods=['POST'])
def analyze_soil():
    data = request.get_json()
    soil_report = data.get("soil_report")
    lat = data.get("lat")
    lon = data.get("lon")
    if not soil_report or not lat or not lon:
        return jsonify({"error": "Incomplete data"}), 400

    # Extract soil classification and properties details
    classification_data = soil_report.get("classification", {})
    soil_classification = classification_data.get("soil_type", "Unknown")
    soil_properties = soil_report.get("properties", [])

    prompt = f"""
    hey {classification_data},{soil_classification},{soil_properties},{lat},{lon} this ar emuy soil report data and location, now i want souil report analyssi, so heading soil report anaalysis central allgin in green bold below it soil type left allgined in bakc bold with roper spacing from heading, infact between each new content proper spacing should be there porper allgiment etc,belwo ti 2-3 points inshgts line by line on soil type and lcoation belwo it green coored tbale of soli parmeters values rnage (hihg,low,normal), normal rnange(ex : just ex : 112-128) 9and tdecide this rnage by seeing carefully from all sources,seeing units carefully and reverifying it) and deescription /comment on rnage porper tbale with columns Pramaster values Rnage (High,Normal,Low) and Description, dont include range(100-110), it si for accurate output study ony belwo it suitbale cropstbale green tbale with spaxcing suitb ale crops lsit in form of table based on soil aprmaters valeu,soil type and location in grene tbale okay below it insights on point for ferltizistion type,irrigation type, agricl;uturla suitbale practices etc.. porper spacing betwene cotnent prpepr rendritn tbale font,bolds etc.. retrvoie in amrodwn format properrenderign on html, all cotnent within ''' and '''and heading size should be big and not small porper spacing and provide the recommended crops as a list and not in text and make the predictions properly based on the lat longi weather there and the soil condition. dont give outputs like (Based on limited information, a detailed suitability assessment requires more data including location specifics and climate data. These are suggestions and further research is advised.)
    Drought-tolerant crops such as Sorghum, Millet, and certain legumes (e.g., beans) may be more suitable, but even these would likely benefit from supplementary irrigation. put atleast some in table.first give inshgts keey insghts ,shoudl not be uselss in short poitns then tbales ,recomended crops ,then again point sdont use paragrpahs,use short points, should be interestign for famrers,report should not be broing,hence porper chart or kkey point representation. all heading subheading big size font and subheading left alligned, and heading centrla allgined and key isnhgts in bullet point use of highlighters and color shcmees to highlight important points (all important points you should highlight by yellow),tables header coor should be green,beautuufl report
    """

    try:
        # Initialize the new Google GenAI client using Gemini 1.5 Flash
        client = genai.Client(api_key="AIzaSyBtXV2xJbrWVV57B5RWy_meKXOA59HFMeY")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        analysis = response.text

        # Remove any triple quotes if present
        if analysis.startswith("'''") and analysis.endswith("'''"):
            analysis = analysis[3:-3]

    except Exception as e:
        analysis = "Gemini analysis not available: " + str(e)

    analysis = markdown.markdown(analysis)
    return jsonify({"analysis": analysis})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
