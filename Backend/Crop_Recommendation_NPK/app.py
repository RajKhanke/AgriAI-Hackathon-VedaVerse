from flask import Flask, render_template, request, jsonify
import joblib
import google.generativeai as genai

# Initialize the Flask app
app = Flask(__name__)

# Load the trained model
gbm_model = joblib.load('gbm_model.pkl')

# Configure Gemini AI
genai.configure(api_key='AIzaSyBtXV2xJbrWVV57B5RWy_meKXOA59HFMeY')
model = genai.GenerativeModel("gemini-1.5-flash")

# Mapping for class decoding
class_mapping = {
    0: 'BANANA', 1: 'BLACKGRAM', 2: 'CHICKPEA', 3: 'COCONUT', 4: 'COFFEE',
    5: 'COTTON', 6: 'JUTE', 7: 'KIDNEYBEANS', 8: 'LENTIL', 9: 'MAIZE',
    10: 'MANGO', 11: 'MOTHBEANS', 12: 'MUNGBEAN', 13: 'MUSKMELON',
    14: 'ORANGE', 15: 'PAPAYA', 16: 'PIGEONPEAS', 17: 'POMEGRANATE',
    18: 'RICE', 19: 'WATERMELON'
}

# AI suggestions from Gemini
def generate_ai_suggestions(pred_crop_name, parameters):
    prompt = (
        f"For the crop {pred_crop_name} based on the input parameters {parameters}, "
        f"Give descritpion of provided crop in justified 3-4 line sparagraph."
        f"After that spacing of one to two lines"
        f"**in the next line** recokemnd foru other crops based on parpameeters as Other recommended crops : crop names in numbvered order. dont include any special character not bold,italic."
    )
    response = model.generate_content(prompt)
    return response.text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    # Get input values from the form
    nitrogen = float(request.form['nitrogen'])
    phosphorus = float(request.form['phosphorus'])
    potassium = float(request.form['potassium'])
    temperature = float(request.form['temperature'])
    humidity = float(request.form['humidity'])
    ph = float(request.form['ph'])
    rainfall = float(request.form['rainfall'])
    location = request.form['location']

    # Prepare the features for the model
    features = [[nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall]]
    predicted_crop_encoded = gbm_model.predict(features)[0]
    predicted_crop = class_mapping[predicted_crop_encoded]

    # Get AI suggestions from Gemini
    parameters = {
        "Nitrogen": nitrogen, "Phosphorus": phosphorus, "Potassium": potassium,
        "Temperature": temperature, "Humidity": humidity, "pH": ph, "Rainfall": rainfall,
        "Location": location
    }
    ai_suggestions = generate_ai_suggestions(predicted_crop, parameters)

    return jsonify({
        'predicted_crop': predicted_crop,
        'ai_suggestions': ai_suggestions,
        'location': location
    })

if __name__ == '__main__':
    app.run(debug=True)
