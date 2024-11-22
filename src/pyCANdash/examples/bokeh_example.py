from bokeh.layouts import layout
from bokeh.models import Div, RangeSlider, Spinner, CustomJS, MultiSelect
from bokeh.plotting import figure, show, output_file, save

# prepare some data
x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
y = [4, 5, 5, 7, 2, 6, 4, 9, 1, 3]

# create plot with circle glyphs
p = figure(x_range=(1, 9), width=1000, height=800)
points = p.scatter(x=x, y=y, size=30, fill_color="#21a7df")

# set up textarea (div)
div = Div(
    text="""
          <p>Select the circle's size using this control element:</p>
          """,
    width=200,
    height=30,
)

# set up spinner
spinner = Spinner(
    title="Circle size",
    low=0,
    high=60,
    step=5,
    value=points.glyph.size,
    width=200,
)
spinner.js_link("value", points.glyph, "size")

# set up RangeSlider
range_slider = RangeSlider(
    title="Adjust x-axis range",
    start=0,
    end=10,
    step=1,
    value=(p.x_range.start, p.x_range.end),
)

range_slider.js_link("value", p.x_range, "start", attr_selector=0)
range_slider.js_link("value", p.x_range, "end", attr_selector=1)

OPTIONS = [ ("1", "foo"),
            ("2", "bar"),
            ("3", "baz"),
            ("4", "quux"),
            ("5", "foo"),
            ("6", "bar"),
            ("7", "baz"),
            ("8", "quux"),
            ("9", "foooo"),
            ("10", "bar"),
            ("11", "baz"),
            ("12", "quux")]

multi_select = MultiSelect(value=["1", "2"], options=OPTIONS, sizing_mode="stretch_both")
multi_select.js_on_change("value", CustomJS(code="""
    console.log('multi_select: value=' + this.value, this.toString())
"""))




# create layout
layout = layout(
    [
        [div, spinner],
        [range_slider],
        [multi_select, p],
    ],
)

#output_file(filename="custom_filename.html", title="Static HTML file")

# show result
show(layout)

#save(layout)

