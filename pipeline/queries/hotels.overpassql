[out:json][timeout:180];
(
  nwr["tourism"~"^(hotel|guest_house|apartment|hostel|motel)$"](43.38,39.62,43.66,40.02);
);
out tags geom qt;
