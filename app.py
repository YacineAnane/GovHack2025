from flask import Flask, render_template
import plotly.graph_objects as go
import plotly.io as pio

app = Flask(__name__)

@app.route("/")
def index():
    # Your Plotly figure
    fig = go.Figure(go.Scattermapbox(
        lat=['38.91427','38.91538','38.91458',
             '38.92239','38.93222','38.90842',
             '38.91931','38.93260','38.91368',
             '38.88516','38.921894','38.93206',
             '38.91275'],
        lon=['-77.02827','-77.02013','-77.03155',
             '-77.04227','-77.02854','-77.02419',
             '-77.02518','-77.03304','-77.04509',
             '-76.99656','-77.042438','-77.02821',
             '-77.01239'],
        mode="markers",
        marker=dict(size=9),
        text=["The coffee bar","Bistro Bohem","Black Cat",
              "Snap","Columbia Heights Coffee","Azi's Cafe",
              "Blind Dog Cafe","Le Caprice","Filter",
              "Peregrine","Tryst","The Coupe",
              "Big Bear Cafe"]
    ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",   # important! Scattermapbox needs a basemap
            center=dict(lat=38.92, lon=-77.07),
            zoom=10
        ),
        margin=dict(l=0, r=0, t=0, b=0)
    )

    # Convert figure to HTML <div>
    fig_html = pio.to_html(fig, full_html=False)

    return render_template("index.html", plot_div=fig_html)


if __name__ == "__main__":
    app.run(debug=True)
