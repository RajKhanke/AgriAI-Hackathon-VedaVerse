from flask import Flask, render_template, request
from markupsafe import Markup
from google import genai

app = Flask(__name__)

# Initialize the Gemini API client using your API key
client = genai.Client(api_key="AIzaSyBtXV2xJbrWVV57B5RWy_meKXOA59HFMeY")


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve farm details
        location = request.form.get('location')
        season = request.form.get('season')
        total_area = request.form.get('total_area')
        language = request.form.get('language', 'English')  # Get selected language with English as default

        # Retrieve crop details
        crop_names = request.form.getlist('crop_name')
        crop_areas = request.form.getlist('crop_area')
        crops = []
        for name, area in zip(crop_names, crop_areas):
            if name.strip() and area.strip():
                crops.append({'name': name.strip(), 'area': area.strip()})

        # Construct a descriptive summary of the crop details
        crop_details = ", ".join([f"{crop['name']} ({crop['area']} acres)" for crop in crops])

        # Build the prompt that instructs the API to generate a fully formatted HTML page with enhanced CSS styling.
        prompt = f"""
        You are a skilled agriculture expert. I am providing you with the following farm details and crop information:

        - Location: {location}
        - Season: {season}
        - Total Farm Area: {total_area} acres
        - Crop Details: {crop_details}

        Using the above input, please generate a fully formatted HTML page with enhanced CSS styling that includes the following sections:
        i dont want any spacing remove extra spaicng if any

        1. **Main Heading:**  
           - A centrally aligned, bold heading in green titled "Crop Swapping Strategies" with no extra spacing before the heading or after the report. Use medium overall spacing, clear font sizes for both headings and points, and ensure the report is easily understandable by farmers. Tables should be designed for optimal readability.

        2. **Current Strategy Statistics:**  
           - A left-aligned, blue bold subheading "Current Strategy Statistics".  
           - Below it, include a green table with columns for:
             - Crop Name
             - Gross Revenue
             - Yearly Production
             - Yearly Expenses
             - Overall Profit Percentage  
           - Populate the table with realistic hypothetical data based on the provided crop details.

        3. **Year Crops Swapping Strategies (3-Year Forecast):**  
           - A left-aligned, blue bold subheading titled "#Year Crops Swapping Strategies".  
           - Create a green table that displays season-wise cropping strategies over the next three years, ensuring clarity with concise headers and data. Incorporate land optimization details (e.g., tomato: 1.5 acres) and consider different cropping seasons such as Rabi and Kharif.

        4. **Swapping Strategy Statistics:**  
           - A left-aligned, blue bold subheading "Swapping Strategy Statistics".  
           - Add a green table showing new strategy data including:
             - Production
             - Gross Income
             - Profit Percentage  
           - Use realistic figures that align with crop swapping strategies.

        5. **Comparative Analysis:**  
           - Include a section with a blue left-aligned subheading "Comparison of Current and Swapped Strategy Statistics".  
           - Present a comparative table clearly outlining differences between the current strategy and the new swapped strategy.

        6. **Insights and Recommendations:**  
           - At the bottom of the page, include a bullet-point list with short, concise sentences offering insights, recommendations, and questions.  
           - Style each bullet point in bold with yellow highlights on key statistics and numbers.  
           - Optimize spacing and margins to ensure a visually clear layout.

        Additionally, design interactive, beautiful, and colorful tables. Increase the font size for headings and reduce excessive spacing to produce a rich, detailed, and farmer-friendly report using realistic data. Do not include any explanations of the changes.

        IMPORTANT: Give the entire response in {language} language. All text, headings, and content should be in {language}.

        IMPORTANT: Do not add any extra spacing at the beginning or end of the response. Remove any extra spacing.
        """

        # Call the Gemini API with the constructed prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        # Extract the generated text (HTML)
        result_html = response.text

        # Remove any extra spacing at the beginning and end of the response
        result_html = result_html.strip()

        # Pass the HTML to the template as 'safe' so it's rendered properly
        return render_template('index.html', result=Markup(result_html))

    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)