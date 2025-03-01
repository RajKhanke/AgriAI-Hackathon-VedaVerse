from flask import Flask, request, render_template, jsonify
import joblib
import pandas as pd

app = Flask(__name__)

# Load the trained LightGBM model
lgb_model = joblib.load('lgb_model_cropseason.pkl')

url='https://drive.google.com/file/d/1_vd4HISZB2h2--CiXKezeWDXHHo2fY23/view?usp=sharing'
data = pd.read_csv('https://drive.usercontent.google.com/download?id={}&export=download&authuser=0&confirm=t'.format(url.split('/')[-2]))

# Extract unique values for states, districts, crops, and seasons
unique_states = data['State'].unique()
unique_crops = data['Crop'].unique()

# Descriptions for each cropping season
season_descriptions = {
    'Kharif': 'Kharif season occurs from June to October, associated with the monsoon. Crops are usually sown at the start of the rainy season.',
    'Rabi': 'Rabi season spans from October to March, during the winter cropping season, with crops like wheat and barley.',
    'Summer': 'Summer season is from April to June, suitable for crops that need warmer temperatures.',
    'Winter': 'Winter cropping season occurs from November to February, including cold-weather crops.',
    'Whole Year': 'Crops can be grown throughout the year, without seasonal limitations.',
    'Autumn': 'Autumn season, from September to November, accommodates crops suited to a post-monsoon environment.'
}

@app.route('/')
def home():
    return render_template('index.html', states=unique_states, crops=unique_crops, seasons=season_descriptions.keys())

@app.route('/filter_districts', methods=['POST'])
def filter_districts():
    state = request.form.get('state')
    filtered_districts = data[data['State'] == state]['District'].unique()
    return jsonify({'districts': list(filtered_districts)})

@app.route('/predict', methods=['POST'])
def predict():
    state = request.form.get('state')
    district = request.form.get('district')
    crop_year = int(request.form.get('crop_year'))
    crop = request.form.get('crop')
    area = float(request.form.get('area'))

    input_data = pd.DataFrame({
        'State': [state],
        'District': [district],
        'Crop_Year': [crop_year],
        'Crop': [crop],
        'Area': [area]
    })

    input_data['State'] = input_data['State'].astype('category')
    input_data['District'] = input_data['District'].astype('category')
    input_data['Crop'] = input_data['Crop'].astype('category')

    predicted_season = lgb_model.predict(input_data)[0]

    # Debug: print the predicted season to console
    print(f"Predicted Season: {predicted_season}")

    # Ensure the predicted season is treated as a string for matching
    predicted_season_str = str(predicted_season)  # Ensure it's a stri

    # Check if the predicted season is in the descriptions
    if predicted_season in season_descriptions:
        season_description = season_descriptions[predicted_season]
    else:
        season_description = 'No description available'

    return render_template('index.html', states=unique_states, crops=unique_crops, seasons=season_descriptions.keys(),
                           predicted_season=predicted_season, season_description=season_description)

if __name__ == '__main__':
    app.run(debug=True)
