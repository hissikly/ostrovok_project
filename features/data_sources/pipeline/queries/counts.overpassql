[out:json][timeout:180];
way["building"](43.38,39.62,43.66,40.02)->.b;
.b out count;
way.b["height"]; out count;
way.b["building:levels"]; out count;
nwr["tourism"~"^(hotel|guest_house|apartment|hostel|motel)$"](43.38,39.62,43.66,40.02); out count;
nwr["tourism"="hotel"](43.38,39.62,43.66,40.02); out count;
