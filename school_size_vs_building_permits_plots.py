import plotly.express as px
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# load data
permits = pd.read_excel('data/20251496-Rawdata-July-20251.xlsb', engine='pyxlsb', sheet_name="Sheet1")  # sheet_name=0 reads the first sheet
suburb = pd.read_csv('data/geojson/australian-suburbs-master/data/suburbs.csv')
school_locs = pd.read_csv('data/dv402-SchoolLocations2025.csv') 
enrollment = pd.read_csv('data/dv403-AllSchoolsEnrolments-2025.csv')


# Merge data
a = permits.groupby('site_postcode__c').agg(
    total_permits=('BASIS_Month_M', 'count'),
    average_permmits_cost= ('Reported_Cost_of_works', 'mean')
).reset_index()

permits_with_location = []

for _, row in a.iterrows():
    location = suburbs[suburbs['postcode'] == row['site_postcode__c']]
    if not location.empty:
        permits_with_location.append({
            'postcode': row['site_postcode__c'],
            'average_reported_cost':row['average_permmits_cost'],
            'total_permits': row['total_permits'],
            'lat': location.iloc[0]['lat'],
            'lng': location.iloc[0]['lng']
        })

permits_with_location = pd.DataFrame(permits_with_location)

school_combined = school_locs.merge(enrollment, left_on="School_Name", right_on="School_Name")

#Plot data

def plot_school_size_vs_building_permits(school_data, building_permit_data):
    pio.renderers.default = "notebook"  # or "browser"

    fig = go.Figure()

    # Layer: schools, size by number of kids
    fig.add_trace(go.Scattermapbox(
        lat=school_data['Y'],
        lon=school_data['X'],
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=school_data['"Grand Total"'],  # size proportional to number of kids
            sizemode='area',
            sizeref=school_data['"Grand Total"'].max() / 50,  # scaling
            color='blue',
            opacity=0.6
        ),
        # hover info with school name and total enrolled students
        text=(
            "School: " + school_data['School_Name'] +
            "<br>Enrolled students: " + school_data['\"Grand Total\"'].astype(str)
        ),
        hoverinfo="text",
        name='Schools'
    ))

    # Layer: permits (average reported cost per postcode/location + total permits)
    fig.add_trace(go.Scattermapbox(
        lat=building_permit_data['lat'],
        lon=building_permit_data['lng'],
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=building_permit_data['average_reported_cost'] / 10000,  # scale cost to marker size
            sizemode='area',
            sizeref=2,
            color='red',
            opacity=0.8
        ),
        # hover info with average cost + total permits
        text=(
            "Avg cost: $" + building_permit_data['average_reported_cost'].round(0).astype(str) +
            "<br>Total permits: " + building_permit_data['total_permits'].astype(str)
        ),
        hoverinfo="text",
        name='Building Permits'
    ))

    # Layout
    fig.update_layout(
        mapbox_style='open-street-map',
        mapbox_zoom=10,
        mapbox_center={
            "lat": school_data['Y'].mean(),
            "lon": school_data['X'].mean()
        },
        margin={"r":0,"t":0,"l":0,"b":0}
    )

    return fig