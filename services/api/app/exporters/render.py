from dataclasses import dataclass
from html import escape
import cairosvg
from app.schemas import Representation


@dataclass(frozen=True)
class Exporter:
    id: str
    name: str
    mime_type: str
    extension: str
    capabilities: tuple[str, ...]
    hardware: str = "No device-specific compatibility validated"

    def render(self, representation: Representation) -> bytes:
        svg = render_svg(representation).encode()
        if self.id == "svg":
            return svg
        if self.id == "pdf":
            return cairosvg.svg2pdf(bytestring=svg)
        return cairosvg.svg2png(bytestring=svg, output_width=1800)


exporters = {e.id: e for e in [Exporter("svg", "Editable SVG", "image/svg+xml", "svg", ("vector", "text", "tactile-oriented")), Exporter("pdf", "Print PDF", "application/pdf", "pdf", ("vector", "print")), Exporter("png", "PNG image", "image/png", "png", ("raster", "preview"))]}


def render_svg(rep: Representation) -> str:
    output = rep.export_settings
    width, height = output.page_width_mm, output.page_height_mm
    canvas_width = 900
    canvas_height = canvas_width * height / width
    available_height = canvas_height - (160 if output.legend else 75)
    ratio = rep.source.width / rep.source.height
    map_width = min(800, available_height * ratio)
    map_height = map_width / ratio
    offset_x, offset_y = (900 - map_width) / 2, 45
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 900 {canvas_height}" role="img" aria-labelledby="title description">', '<title id="title">Accessible map adaptation</title>', f'<desc id="description">{escape(rep.description)}</desc>', '<defs><pattern id="dots" width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="6" cy="6" r="1.5" fill="black"/></pattern><pattern id="diagonal" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0 12L12 0" stroke="black" stroke-width="1"/></pattern></defs>', f'<rect width="900" height="{canvas_height}" fill="white"/>']
    categories = set()
    for element in rep.elements:
        if not element.visible:
            continue
        categories.add(element.category)
        points = [(offset_x + x * map_width, offset_y + y * map_height) for x, y in element.geometry.coordinates]
        stroke = output.line_width * 900 / width
        dash = ' stroke-dasharray="10 7"' if element.category == "rivers" else ' stroke-dasharray="3 5"' if element.category == "roads" else ""
        texture = element.style.texture if element.style.texture != "none" else output.texture
        fill = f'url(#{texture})' if element.category == "regions" and texture != "none" else "none"
        parts.append(f'<g id="{escape(element.id, quote=True)}"><title>{escape(element.label or element.category)}: {escape(element.description)}</title>')
        if element.geometry.type == "point":
            x, y = points[0]
            if element.category != "labels":
                parts.append(f'<circle cx="{x}" cy="{y}" r="{output.symbol_size}" fill="white" stroke="black" stroke-width="{stroke}"/>')
        else:
            paths = [points]
            if element.geometry.type == "multipart":
                paths += [[(offset_x + x * map_width, offset_y + y * map_height) for x, y in part] for part in element.geometry.parts]
            for path in paths:
                tag = "polygon" if element.geometry.type == "polygon" else "polyline"
                coordinates = " ".join(f"{x:.2f},{y:.2f}" for x, y in path)
                parts.append(f'<{tag} points="{coordinates}" fill="{fill}" stroke="black" stroke-width="{stroke}" stroke-linejoin="round" stroke-linecap="round"{dash}/>')
        if element.label:
            x, y = points[0]
            parts.append(f'<text x="{min(x + 8, 760)}" y="{max(y - 8, 22)}" font-family="sans-serif" font-size="{output.label_size}" fill="black">{escape(element.label)}</text>')
        parts.append('</g>')
    if output.legend:
        y = canvas_height - 100
        parts.append(f'<text x="50" y="{y}" font-size="18" font-family="sans-serif" font-weight="bold">Legend</text>')
        for index, category in enumerate(sorted(categories)):
            x, yy = 50 + (index % 4) * 205, y + 30 + (index // 4) * 30
            dash = ' stroke-dasharray="10 7"' if category == "rivers" else ' stroke-dasharray="3 5"' if category == "roads" else ""
            parts.append(f'<path d="M{x} {yy - 5}h30" stroke="black" stroke-width="2"{dash}/><text x="{x + 40}" y="{yy}" font-size="14" font-family="sans-serif">{category.title()}</text>')
    parts.append('</svg>')
    return "".join(parts)


def validate_layout(rep: Representation) -> list[str]:
    warnings = []
    points = [(e, e.geometry.coordinates[0]) for e in rep.elements if e.visible]
    for index, (element, p) in enumerate(points):
        for other, q in points[index + 1:]:
            distance = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 * min(rep.export_settings.page_width_mm, rep.export_settings.page_height_mm)
            if distance < rep.export_settings.minimum_spacing_mm:
                warnings.append("Some feature anchors are closer than the target minimum spacing. Review overlapping lines and labels manually.")
                return warnings
    if rep.export_settings.profile == "swell":
        warnings.append("Swell-paper-oriented output only. Check fill density, line spacing and labels with your production specialist.")
    return warnings
