/**
 * The City Pack's boxes for the smokes (cities/<SAJAG_CITY, default mumbai>/city.json): the camera envelope the idle
 * checks hold the canvas to, and the spatial query that reads the city's road network. Smokes read the pack instead
 * of carrying a city's longitudes of their own.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const CITY_ID = process.env.SAJAG_CITY || 'mumbai';
const pack = JSON.parse(readFileSync(path.resolve(HERE, '..', '..', '..', '..', 'cities', CITY_ID, 'city.json'), 'utf8'));

/** { minLon, maxLon, minLat, maxLat } — the pack's bbox. */
export const CITY_BOX = { minLon: pack.bbox.west, maxLon: pack.bbox.east, minLat: pack.bbox.south, maxLat: pack.bbox.north };

/** `min_lon=…&min_lat=…&max_lon=…&max_lat=…` for GET /api/v1/spatial/segments. */
export const SEGMENTS_QUERY = `min_lon=${CITY_BOX.minLon}&min_lat=${CITY_BOX.minLat}&max_lon=${CITY_BOX.maxLon}&max_lat=${CITY_BOX.maxLat}`;

/** The city centre (lon, lat). */
export const CITY_CENTRE = { lon: pack.centre.lon, lat: pack.centre.lat };
