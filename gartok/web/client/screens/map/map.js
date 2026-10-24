// The map, opened on a save: the guild and where each band stands. Step 8 draws the map itself.
"use strict";

function bandLine(g) {
  if (!g.order) return `at ${esc(g.node)}`;
  return g.order.dest ? `at ${esc(g.node)}, on the way to ${esc(g.order.dest)}` : `at ${esc(g.node)} · ${esc(g.order.kind)}`;
}

api("/api/map/state").then(M => {
  $("guildname").textContent = M.meta.name;
  $("clock").textContent = `Day ${M.meta.day} · ${String(M.meta.hour).padStart(2, "0")}:00`;
  $("bands").innerHTML = M.groups.map(g => `<div class="leather band"><h2>${esc(g.name)}</h2>
    <div class="where">${bandLine(g)}</div>
    <div class="faces">${g.members.map(u => `<div class="medal ${u.leader ? "lead" : ""}" title="${esc(u.name)}">${face(u.portrait, u.name)}</div>`).join("")}</div></div>`).join("");
});
