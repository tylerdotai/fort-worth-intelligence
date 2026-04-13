"""
CityGML 3.0 encoding utilities for Fort Worth Intelligence.

Converts resolved address records into OGC CityGML 3.0 XML documents.
Base standard: https://www.ogc.org/standard/citygml/
"""
from lxml import etree as ET
from datetime import datetime, timezone

NAMESPACE = "https://fwintelligence.city/ont/v1"
GML_NS = "http://www.opengis.net/gml/3.2"
FW_NS = "https://fwintelligence.city/ont/v1"
SCHEMA_LOCATION = "https://fwintelligence.city/ont/v1"

GML_NSMAP = {
    "gml": GML_NS,
    "fw": FW_NS,
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def cid(obj_id: str) -> str:
    """Safe XML ID from a string — lowercase, dashes/underscores normalized."""
    return "".join(c if c.isalnum() else "_" for c in obj_id.lower().replace("-", "_").replace(":", "_"))


def gml_id(prefix: str, local_id: str) -> str:
    """Create a gml:id value: fw_prefix_localid."""
    safe = cid(local_id)
    return f"fw_{prefix}_{safe}"


def citymodel_member(resolved: dict, entity_id: str) -> ET._Element:
    """
    Wrap a resolved address as a CityGML CityModel member.

    Generates:
    <CityModel gml:id="cm_{entity_id}">
      <member>
        <Site gml:id="s_{entity_id}">
          <externalDocuments> — provenance
          <validFrom/validTo> — temporal
          <fw:parcelRef> — TAD parcel reference
          <fw:councilDistrictRef> — council district
          <address> — Address
        </Site>
      </member>
      <metaDataMetadata> — schema version, snapshot
    </CityModel>
    """
    qn_gml = lambda tag: f"{{{GML_NS}}}{tag}"
    qn_fw = lambda tag: f"{{{FW_NS}}}{tag}"

    query_addr = resolved.get("query_address", entity_id)
    meta = resolved.get("_meta", {})
    snapshot_id = meta.get("snapshot_id", "unknown")
    parcel = resolved.get("parcel") or {}
    council = resolved.get("council_district") or {}
    school = resolved.get("school_district") or {}
    coords = resolved.get("coordinates") or {}

    root = ET.Element(qn_gml("CityModel"), nsmap=GML_NSMAP)
    root.set(qn_gml("id"), gml_id("cm", entity_id))

    valid_from = parcel.get("valid_from") or f"{datetime.now(timezone.utc).year}-01-01"
    valid_to = parcel.get("valid_to") or f"{datetime.now(timezone.utc).year}-12-31"

    # ── Site member ────────────────────────────────────────────────────────────
    site = ET.SubElement(root, qn_gml("member"))
    site_elem = ET.SubElement(site, qn_gml("Site"))
    site_elem.set(qn_gml("id"), gml_id("site", entity_id))

    # External document — provenance
    ext_doc = ET.SubElement(site_elem, qn_gml("externalDocuments"))
    doc = ET.SubElement(ext_doc, qn_gml("Document"))
    doc.set(qn_gml("id"), gml_id("doc", entity_id))
    ET.SubElement(doc, qn_gml("name")).text = f"Fort Worth Intelligence - {snapshot_id}"
    ET.SubElement(doc, qn_gml("description")).text = f"Address: {query_addr}"

    # Temporal validity window
    ET.SubElement(site_elem, qn_gml("validFrom")).text = valid_from
    if valid_to:
        ET.SubElement(site_elem, qn_gml("validTo")).text = valid_to

    # ── Fort Worth ADE attributes ─────────────────────────────────────────────
    if parcel.get("pidn"):
        parcel_ref = ET.SubElement(site_elem, qn_fw("parcelRef"))
        parcel_ref.set(qn_gml("href"), f"#{gml_id('parcel', parcel['pidn'])}")
        ET.SubElement(parcel_ref, qn_fw("pidn")).text = parcel.get("pidn")
        if parcel.get("owner_name"):
            ET.SubElement(parcel_ref, qn_fw("ownerName")).text = parcel.get("owner_name")
        if parcel.get("market_value"):
            ET.SubElement(parcel_ref, qn_fw("marketValue")).text = str(parcel.get("market_value"))
        if parcel.get("year_built"):
            ET.SubElement(parcel_ref, qn_fw("yearBuilt")).text = str(parcel.get("year_built"))

    if council.get("district_number"):
        cd_ref = ET.SubElement(site_elem, qn_fw("councilDistrictRef"))
        cd_ref.set(qn_gml("href"), f"#{gml_id('council', str(council['district_number']))}")
        ET.SubElement(cd_ref, qn_fw("councilMember")).text = council.get("councilmember", "")
        ET.SubElement(cd_ref, qn_fw("email")).text = council.get("email", "")

    if school.get("name"):
        sd_ref = ET.SubElement(site_elem, qn_fw("schoolDistrictRef"))
        ET.SubElement(sd_ref, qn_fw("schoolName")).text = school.get("name")

    # ── Address + coordinates ─────────────────────────────────────────────────
    addr_elem = ET.SubElement(site_elem, qn_gml("address"))
    addr_space = ET.SubElement(addr_elem, qn_gml("Address"))
    addr_space.set(qn_gml("id"), gml_id("addr", entity_id))
    ET.SubElement(addr_space, qn_gml("address")).text = query_addr

    if coords.get("lat") and coords.get("lon"):
        pos = ET.SubElement(addr_space, qn_gml("location"))
        pos_pt = ET.SubElement(pos, qn_gml("Point"))
        pos_pt.set(qn_gml("id"), gml_id("pt", entity_id))
        pos_pt.set("srsDimension", "2")
        pos_pt.set("srsName", "EPSG:4326")
        ET.SubElement(pos_pt, qn_gml("pos")).text = f"{coords['lon']} {coords['lat']}"

    # ── Geometry: council district polygon ────────────────────────────────────
    cd_geo = council.get("geometry_geojson")
    if cd_geo and cd_geo.get("type") == "Polygon":
        geom_elem = ET.SubElement(site_elem, qn_gml("lod0Geometry"))
        poly = ET.SubElement(geom_elem, qn_gml("Polygon"))
        poly.set(qn_gml("id"), gml_id("poly", entity_id))
        poly.set("srsName", f"EPSG:{council.get('srid', '4326')}")
        ext = ET.SubElement(poly, qn_gml("exterior"))
        ring = ET.SubElement(ext, qn_gml("LinearRing"))
        ring.set(qn_gml("id"), gml_id("ring", entity_id))
        coords_list = []
        for coord_pair in cd_geo["coordinates"][0]:
            coords_list.append(f"{coord_pair[0]} {coord_pair[1]}")
        ET.SubElement(ring, qn_gml("posList")).text = " ".join(coords_list)

    # ── MetaData ─────────────────────────────────────────────────────────────
    mm = ET.SubElement(root, qn_gml("metaDataMetadata"))
    mm_info = ET.SubElement(mm, qn_fw("GenerationInformation"))
    ET.SubElement(mm_info, qn_fw("schemaVersion")).text = resolved.get("schema_version", "1.0")
    ET.SubElement(mm_info, qn_fw("snapshotId")).text = snapshot_id
    ET.SubElement(mm_info, qn_fw("resolvedAt")).text = resolved.get("resolved_at", "")

    return root


def citygml_document(resolved: dict, entity_id: str) -> str:
    """
    Serialize a resolved address as a CityGML 3.0 XML document.
    """
    root = citymodel_member(resolved, entity_id)
    # Set schema location
    root.set(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
        f"{SCHEMA_LOCATION} https://www.citygml.org/citygml/3.0.1/citygml.xsd"
    )
    xml_decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
    return xml_decl + ET.tostring(root, pretty_print=True, encoding="unicode")
