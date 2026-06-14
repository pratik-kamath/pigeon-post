import { apiFetch } from "./client";

export interface City {
  name: string;
  lat: number;
  lon: number;
}

export const fetchCities = () => apiFetch<City[]>("/cities");
