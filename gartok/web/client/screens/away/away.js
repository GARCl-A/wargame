// A screen the browser does not draw yet: where the band went, and back to the map.
"use strict";

api("/api/away/state").then(A => {
  $("away").classList.toggle("fight", A.fight);
  $("awayplace").textContent = `${A.band} · ${A.place}`;
  $("awayicon").style.setProperty("--icon", `url(/assets/icons/${A.icon}.svg)`);
  $("awaytitle").textContent = A.title;
  $("awayline").textContent = A.line;
});

async function back() {
  await api("/api/away/back", {});
  location.reload();
}
$("awayback").onclick = back;
addEventListener("keydown", e => { if (e.key === "Escape" || e.key === "Enter") back(); });
