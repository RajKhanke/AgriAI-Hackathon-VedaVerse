from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import joblib
import numpy as np

app = Flask(__name__)

url='https://drive.google.com/file/d/1_vd4HISZB2h2--CiXKezeWDXHHo2fY23/view?usp=sharing'
df = pd.read_csv('https://drive.usercontent.google.com/download?id={}&export=download&authuser=0&confirm=t'.format(url.split('/')[-2]))

for column in ['State', 'District', 'Crop', 'Season']:
    df[column] = df[column].str.strip()

# Load the model for predictions
model_filename = 'lgb_model_cropforecastinghyperparamters__33333.pkl'
model = joblib.load(model_filename)

# Use a 2% sample for faster processing
sampled_df = df.sample(frac=0.02, random_state=42)

@app.route('/')
def index():
    states = sampled_df['State'].unique()
    crops = sampled_df['Crop'].unique()
    seasons = sampled_df['Season'].unique()
    return render_template('index.html', states=states, crops=crops, seasons=seasons)

@app.route('/filter_districts', methods=['POST'])
def filter_districts():
    state = request.form['state']
    districts = sampled_df[sampled_df['State'] == state]['District'].unique()
    return jsonify({'districts': list(districts)})

@app.route('/predict', methods=['POST'])
def predict():
    state = request.form['state']
    district = request.form['district']
    crop_year = int(request.form['crop_year'])
    season = request.form['season']
    crop = request.form['crop']
    area = float(request.form['area'])

    # Prepare input for prediction
    input_data = pd.DataFrame({
        'State': [state],
        'District': [district],
        'Crop_Year': [crop_year],
        'Season': [season],
        'Crop': [crop],
        'Area': [area]
    })

    # Ensure consistent categories with the original DataFrame
    input_data['State'] = input_data['State'].astype(pd.CategoricalDtype(categories=df['State'].unique()))
    input_data['District'] = input_data['District'].astype(pd.CategoricalDtype(categories=df['District'].unique()))
    input_data['Season'] = input_data['Season'].astype(pd.CategoricalDtype(categories=df['Season'].unique()))
    input_data['Crop'] = input_data['Crop'].astype(pd.CategoricalDtype(categories=df['Crop'].unique()))

    # Make prediction
    prediction = model.predict(input_data)[0]
    prediction_tons = max(0, round(prediction, 2))  # Ensure prediction is non-negative

    # Calculate production/area ratio
    nearest_area = find_nearest_area(state, district)
    production_ratio = round((prediction_tons / nearest_area), 2)
    ratio_category = categorize_production_ratio(production_ratio)

    # Generate updated graphs based on the selected state and district
    pie_chart = generate_pie_chart(state, district, crop)
    area_vs_production = generate_area_vs_production(state, district)
    season_vs_production = generate_season_vs_production(state, district)
    top_states_by_production = generate_top_states_plot()
    yearly_violin_plot = generate_yearly_violin_plot()
    crop_year_vs_production = generate_crop_year_vs_production(state, district)

    # Create gauge chart for the production ratio
    gauge_chart = generate_gauge_chart(production_ratio, ratio_category)

    # Hardcoded suggestions based on production ratio
    suggestions = generate_suggestions(ratio_category, crop, district)

    return render_template('output.html',
                           prediction=prediction_tons,
                           ratio=production_ratio,
                           pie_chart_html=pio.to_html(pie_chart, full_html=False),
                           season_vs_production_html=pio.to_html(season_vs_production, full_html=False),
                           area_vs_production_html=pio.to_html(area_vs_production, full_html=False),
                           top_states_html=pio.to_html(top_states_by_production, full_html=False),
                           yearly_violin_plot_html=pio.to_html(yearly_violin_plot, full_html=False),
                           crop_year_vs_production_html=pio.to_html(crop_year_vs_production, full_html=False),
                           gauge_chart_html=pio.to_html(gauge_chart, full_html=False),
                           suggestions=suggestions)


def find_nearest_area(state, district):
    # Calculate the nearest similar area for the district using average
    district_data = sampled_df[(sampled_df['State'] == state) & (sampled_df['District'] == district)]
    return district_data['Area'].mean()

def categorize_production_ratio(ratio):
    if ratio <= 2:
        return 'Very Low'
    elif ratio <= 4:
        return 'Low'
    elif ratio <= 6:
        return 'Normal'
    elif ratio <= 8:
        return 'High'
    else:
        return 'Very High'

def generate_suggestions(category, crop, district):
    suggestions = {
        'Very Low': f"Increase soil nutrients and irrigation efficiency. Consider crop rotation strategies. {crop} is not suitable for {district} based on the given conditions and season. Try advanced farming methods or consider growing alternative crops that are better suited to this region.",
        'Low': f"Optimize seed selection and planting techniques. {crop} is somewhat suitable for {district}, but production may be low. Monitor soil moisture regularly and apply precise farming techniques. Current strategies may need improvement for better yields.",
        'Normal': f"Maintain current practices but focus on improving pest control and irrigation. {crop} is generally performing well in {district}. Production and profit depend heavily on farming practices and weather conditions, but there is potential for increased revenue.",
        'High': f"Consider diversifying crops or expanding production. Explore more efficient harvesting methods to optimize yield and profitability. {crop} thrives in {district}, and with better mechanization or workforce management, you can further boost production and income potential.",
        'Very High': f"{crop} is performing exceptionally well in {district}. Explore export opportunities to maximize profitability. Optimize production processes to sustain high yields while minimizing additional inputs. Consider expanding into new markets, and explore ways to reduce production costs, such as through precision farming or automation."
    }
    return suggestions.get(category, "No suggestions available.")


def generate_gauge_chart(ratio, category):
    colors = ["#ff0000", "#ff6666", "#ffa500", "#ffff00", "#32cd32"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=ratio,
        title={'text': "Production Ratio"},
        delta={'reference': 5},
        gauge={'axis': {'range': [None, 10]},
               'bar': {'color': "darkblue"},
               'steps': [{'range': [0, 2], 'color': colors[0]},
                         {'range': [2, 4], 'color': colors[1]},
                         {'range': [4, 6], 'color': colors[2]},
                         {'range': [6, 8], 'color': colors[3]},
                         {'range': [8, 10], 'color': colors[4]}]}))
    return fig

def generate_pie_chart(state, district, crop):
    filtered_data = sampled_df[(sampled_df['State'] == state) & (sampled_df['District'] == district)]
    crop_data = filtered_data.groupby('Crop')['Production'].sum().reset_index()
    crop_data['Percentage'] = (crop_data['Production'] / crop_data['Production'].sum()) * 100
    crop_data = crop_data[crop_data['Percentage'] > 3]
    fig = px.pie(crop_data, names='Crop', values='Production', title='Popular Crops in the Given Region')
    return fig

def generate_season_vs_production(state, district):
    filtered_data = sampled_df[(sampled_df['State'] == state) & (sampled_df['District'] == district)]
    fig = px.bar(filtered_data, x='Season', y='Production', title='Season vs Production (Sum for All Crops)')
    fig.update_traces(marker_color='darkblue')
    return fig

def generate_area_vs_production(state, district):
    filtered_data = sampled_df[(sampled_df['State'] == state) & (sampled_df['District'] == district)]
    fig = px.density_heatmap(filtered_data, x='Area', y='Production', title='Area vs Production (Hexbin Plot)',
                             range_x=[0, 10000], nbinsx=5)
    return fig

def generate_top_states_plot():
    state_data = sampled_df.groupby('State')['Production'].sum().reset_index()
    top_states = state_data.nlargest(10, 'Production')
    fig = px.bar(top_states, x='State', y='Production', title='Top 10 States by Production (Overall)')
    return fig

def generate_yearly_violin_plot():
    filtered_data = sampled_df[sampled_df['Crop_Year'] >= 2014]
    fig = px.violin(filtered_data, x='Crop_Year', y='Production', title='Violin Plot: Overall Production (2014-2023)')
    return fig

def generate_crop_year_vs_production(state, district):
    filtered_data = sampled_df[sampled_df['Crop_Year'] >= 2014]
    fig = px.bar(filtered_data, x='Crop_Year', y='Production', title='Year vs Production Count (2014-2023)',
                 labels={'Crop_Year': 'Year', 'Production': 'Production Count'})
    fig.update_traces(marker_color='darkblue')
    return fig

if __name__ == '__main__':
    app.run(debug=True)
