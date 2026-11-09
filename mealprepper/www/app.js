const state = {
  board: null,
  panel: "pantry",
  draft: emptyDraft(),
};

const panels = {
  pantry: document.querySelector("#panel-pantry"),
  recipes: document.querySelector("#panel-recipes"),
  plan: document.querySelector("#panel-plan"),
};
const notice = document.querySelector("#notice");

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => showPanel(button.dataset.panel));
});
document.querySelector("#ingredient-form").addEventListener("submit", saveIngredient);
document.querySelector("#pantry-filter").addEventListener("input", renderPantry);
document.querySelector("#recipe-form").addEventListener("submit", saveRecipe);
document.querySelector("#add-line").addEventListener("click", addDraftLine);
document.querySelector("#recipe-reset").addEventListener("click", () => {
  state.draft = emptyDraft();
  fillRecipeForm();
});
document.querySelector("#plan-start").addEventListener("change", reloadPlan);
document.querySelector("#plan-days").addEventListener("change", reloadPlan);

run(() => loadBoard());

function emptyDraft() {
  return { id: null, title: "", servings: 2, steps: "", lines: [] };
}

function showPanel(name) {
  state.panel = name;
  for (const [key, panel] of Object.entries(panels)) {
    panel.hidden = key !== name;
  }
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.panel === name);
  });
}

async function loadBoard() {
  const params = new URLSearchParams();
  const start = document.querySelector("#plan-start").value;
  const days = document.querySelector("#plan-days").value;
  if (start) params.set("start", start);
  if (days) params.set("days", days);
  const query = params.toString();
  state.board = await api("/api/board" + (query ? `?${query}` : ""));
  const startInput = document.querySelector("#plan-start");
  const daysInput = document.querySelector("#plan-days");
  if (!startInput.value) startInput.value = state.board.start;
  if (!daysInput.value) daysInput.value = String(state.board.default_days);
  render();
}

function render() {
  document.querySelector("#season-now").textContent =
    `Saison im ${state.board.month_label}. Vorgabe ${state.board.default_people} Personen.`;
  renderPantry();
  renderRecipeFormChoices();
  renderRecipes();
  renderPlan();
}

function renderPantry() {
  const query = document.querySelector("#pantry-filter").value.trim().toLowerCase();
  const list = document.querySelector("#pantry-list");
  list.replaceChildren();
  const items = state.board.ingredients.filter((item) => item.name.toLowerCase().includes(query));
  if (!items.length) {
    list.append(el("p", { class: "hint" }, ["Keine Zutat gefunden."]));
    return;
  }
  for (const item of items) {
    const quantity = el("input", { type: "number", min: "0", step: "0.01", value: String(item.pantry_quantity) });
    const bestBefore = el("input", { type: "date", value: item.best_before || "" });
    const months = monthFields(item.season_months);
    const card = el("article", { class: "item" }, [
      el("header", {}, [
        el("div", {}, [
          el("h2", {}, [item.name]),
          el("p", { class: "meta" }, [seasonText(item)]),
        ]),
        badgesFor(item),
      ]),
      el("div", { class: "qty" }, [
        el("label", {}, ["Menge", quantity]),
        el("label", {}, ["Haltbar bis", bestBefore]),
      ]),
      el("details", {}, [
        el("summary", {}, ["Saison ändern"]),
        el("fieldset", { class: "months" }, [el("legend", {}, ["Monate"]), ...months]),
      ]),
      el("div", { class: "row-actions" }, [
        el("button", { type: "button", onclick: () => savePantry(item, quantity, bestBefore, months) }, ["Speichern"]),
        el("button", { type: "button", class: "quiet", onclick: () => removeIngredient(item) }, ["Löschen"]),
      ]),
    ]);
    list.append(card);
  }
}

function renderRecipeFormChoices() {
  const select = document.querySelector("#line-ingredient");
  const current = select.value;
  select.replaceChildren();
  for (const item of state.board.ingredients) {
    select.append(el("option", { value: String(item.id) }, [`${item.name} (${item.season_label})`]));
  }
  if (current) select.value = current;
}

function renderRecipes() {
  const list = document.querySelector("#recipe-list");
  list.replaceChildren();
  if (!state.board.recipes.length) {
    list.append(el("p", { class: "hint" }, ["Noch kein Rezept."]));
    return;
  }
  for (const recipe of state.board.recipes) {
    const lines = recipe.ingredients.length
      ? recipe.ingredients.map((item) => el("li", {}, [ingredientStatus(item, item.amount)]))
      : [el("li", {}, ["Ohne Zutaten"])];
    list.append(el("article", { class: `item ${recipe.cookable ? "is-cookable" : "is-not-cookable"}` }, [
      el("header", {}, [
        el("div", {}, [
          el("h2", {}, [recipe.title]),
          el("p", { class: "meta" }, [`${recipe.servings} Portionen`]),
        ]),
        el("span", { class: `badge ${recipe.cookable ? "ok" : "off"}` }, [
          recipe.cookable ? "Jetzt kochbar" : "Nicht kochbar",
        ]),
      ]),
      recipe.steps ? el("p", {}, [recipe.steps]) : el("span", {}, []),
      el("ul", { class: "lines" }, lines),
      el("div", { class: "row-actions" }, [
        el("button", { type: "button", onclick: () => editRecipe(recipe) }, ["Bearbeiten"]),
        el("button", { type: "button", class: "quiet", onclick: () => removeRecipe(recipe) }, ["Löschen"]),
      ]),
    ]));
  }
}

function renderPlan() {
  const list = document.querySelector("#plan-list");
  list.replaceChildren();
  for (const day of state.board.days) {
    list.append(el("article", { class: "item" }, [
      el("h2", {}, [`${day.weekday}, ${formatDay(day.date)}`]),
      mealBlock(day, "lunch", "Mittag"),
      mealBlock(day, "dinner", "Abend"),
    ]));
  }
}

function mealBlock(day, meal, label) {
  const slot = day.meals[meal];
  const select = el("select", {}, [
    el("option", { value: "" }, ["Kein Rezept"]),
    ...state.board.recipes.map((recipe) => el("option", {
      value: String(recipe.id),
      selected: slot && slot.recipe_id === recipe.id ? "selected" : null,
    }, [`${recipe.title} (${recipe.cookable ? "kochbar" : "nicht kochbar"})`])),
  ]);
  if (slot) select.value = String(slot.recipe_id);
  const people = el("input", {
    type: "number",
    min: "1",
    max: "99",
    value: String(slot ? slot.people : state.board.default_people),
  });
  const hint = el("div", { class: "hint" }, []);
  const refresh = () => fillHint(hint, select.value);
  select.addEventListener("change", refresh);
  refresh();
  return el("div", { class: "meal" }, [
    el("div", { class: "meal-top" }, [
      el("strong", {}, [label]),
      slot && slot.source === "manual" ? el("span", { class: "badge" }, ["von Hand"]) : el("span", {}, []),
    ]),
    el("label", {}, ["Rezept", select]),
    el("label", {}, ["Personen", people]),
    hint,
    el("div", { class: "row-actions" }, [
      el("button", { type: "button", onclick: () => savePlan(day.date, meal, select, people) }, ["Speichern"]),
      el("button", { type: "button", class: "quiet", onclick: () => clearPlan(day.date, meal) }, ["Leeren"]),
    ]),
  ]);
}

function fillHint(hint, recipeId) {
  hint.replaceChildren();
  if (!recipeId) {
    hint.textContent = "Kein Rezept gewählt.";
    return;
  }
  const recipe = state.board.recipes.find((item) => String(item.id) === String(recipeId));
  if (!recipe) return;
  hint.append(el("p", {}, [
    recipe.cookable
      ? "Jetzt kochbar: jede Zutat ist saisonal oder liegt im Vorrat."
      : "Nicht kochbar: eine Zutat ist weder saisonal noch im Vorrat.",
  ]));
  for (const item of recipe.ingredients) {
    hint.append(el("p", {}, [ingredientStatus(item, item.amount).textContent]));
  }
}

function ingredientStatus(item, amount) {
  const stock = item.pantry_quantity > 0
    ? `Vorrat ${formatQty(item.pantry_quantity)} ${item.unit}`.trim()
    : "kein Vorrat";
  const season = item.in_season ? "Saison" : "nicht saisonal";
  const expired = item.best_before && item.best_before < state.board.today ? ", MHD abgelaufen" : "";
  return el("span", {}, [
    `${item.name}: ${formatQty(amount)} ${item.unit}, ${season}, ${stock}${expired}`.replace(/\s+/g, " ").trim(),
  ]);
}

function badgesFor(item) {
  const nodes = [el("span", { class: `badge ${item.in_season ? "ok" : "off"}` }, [item.in_season ? "Saison" : "nicht saisonal"])];
  if (item.pantry_quantity > 0) {
    nodes.push(el("span", { class: "badge pantry" }, [`Vorrat ${formatQty(item.pantry_quantity)} ${item.unit}`.trim()]));
  }
  if (item.best_before && item.best_before < state.board.today) {
    nodes.push(el("span", { class: "badge expired" }, ["MHD abgelaufen"]));
  }
  return el("div", { class: "badges" }, nodes);
}

function seasonText(item) {
  const unit = item.unit ? ` · ${item.unit}` : "";
  return `${item.season_label}${unit}`;
}

function monthFields(selected) {
  const names = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  return names.map((name, index) => {
    const input = el("input", { type: "checkbox", value: String(index + 1) });
    input.checked = selected.includes(index + 1);
    return el("label", {}, [input, name]);
  });
}

function checkedMonths(fields) {
  return fields
    .map((field) => field.querySelector("input"))
    .filter((input) => input && input.checked)
    .map((input) => Number(input.value));
}

async function saveIngredient(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  await run(async () => {
    await api("/api/ingredients", {
      method: "POST",
      body: JSON.stringify({
        name: data.get("name"),
        unit: data.get("unit"),
        season_months: [...form.querySelectorAll("input[name=season]:checked")].map((input) => Number(input.value)),
      }),
    });
    form.reset();
    await loadBoard();
    setNotice("Zutat gespeichert.");
  });
}

async function savePantry(item, quantity, bestBefore, months) {
  await run(async () => {
    await api("/api/pantry", {
      method: "PUT",
      body: JSON.stringify({
        ingredient_id: item.id,
        quantity: quantity.value,
        best_before: bestBefore.value,
      }),
    });
    await api(`/api/ingredients/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: item.name,
        unit: item.unit,
        season_months: checkedMonths(months),
      }),
    });
    await loadBoard();
    setNotice(`${item.name} gespeichert.`);
  });
}

async function removeIngredient(item) {
  if (!window.confirm(`${item.name} löschen?`)) return;
  await run(async () => {
    await api(`/api/ingredients/${item.id}`, { method: "DELETE" });
    await loadBoard();
    setNotice(`${item.name} gelöscht.`);
  });
}

function addDraftLine() {
  const ingredientId = Number(document.querySelector("#line-ingredient").value);
  const quantity = Number(String(document.querySelector("#line-quantity").value).replace(",", "."));
  if (!ingredientId || !(quantity > 0)) {
    setNotice("Menge im Rezept muss grösser als 0 sein.", true);
    return;
  }
  const existing = state.draft.lines.find((line) => line.ingredient_id === ingredientId);
  if (existing) existing.quantity = quantity;
  else state.draft.lines.push({ ingredient_id: ingredientId, quantity });
  renderDraftLines();
}

function renderDraftLines() {
  const list = document.querySelector("#recipe-lines");
  list.replaceChildren();
  for (const line of state.draft.lines) {
    const ingredient = state.board.ingredients.find((item) => item.id === line.ingredient_id);
    const name = ingredient ? ingredient.name : "Zutat";
    list.append(el("li", {}, [
      `${name}: ${formatQty(line.quantity)} ${ingredient ? ingredient.unit : ""}`.trim(),
      " ",
      el("button", {
        type: "button",
        class: "quiet",
        onclick: () => {
          state.draft.lines = state.draft.lines.filter((item) => item !== line);
          renderDraftLines();
        },
      }, ["Entfernen"]),
    ]));
  }
}

function editRecipe(recipe) {
  state.draft = {
    id: recipe.id,
    title: recipe.title,
    servings: recipe.servings,
    steps: recipe.steps,
    lines: recipe.ingredients.map((item) => ({ ingredient_id: item.id, quantity: item.amount })),
  };
  fillRecipeForm();
  showPanel("recipes");
  document.querySelector("#recipe-form").scrollIntoView({ behavior: "smooth" });
}

function fillRecipeForm() {
  const form = document.querySelector("#recipe-form");
  form.querySelector("[name=title]").value = state.draft.title;
  form.querySelector("[name=servings]").value = String(state.draft.servings);
  form.querySelector("[name=steps]").value = state.draft.steps;
  document.querySelector("#recipe-form-title").textContent = state.draft.id ? "Rezept bearbeiten" : "Rezept";
  renderDraftLines();
}

async function saveRecipe(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    title: form.querySelector("[name=title]").value,
    servings: Number(form.querySelector("[name=servings]").value),
    steps: form.querySelector("[name=steps]").value,
    ingredients: state.draft.lines.map((line) => ({
      ingredient_id: line.ingredient_id,
      quantity: line.quantity,
    })),
  };
  await run(async () => {
    if (state.draft.id) {
      await api(`/api/recipes/${state.draft.id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/recipes", { method: "POST", body: JSON.stringify(payload) });
    }
    state.draft = emptyDraft();
    fillRecipeForm();
    await loadBoard();
    setNotice("Rezept gespeichert.");
  });
}

async function removeRecipe(recipe) {
  if (!window.confirm(`${recipe.title} löschen?`)) return;
  await run(async () => {
    await api(`/api/recipes/${recipe.id}`, { method: "DELETE" });
    if (state.draft.id === recipe.id) {
      state.draft = emptyDraft();
      fillRecipeForm();
    }
    await loadBoard();
    setNotice("Rezept gelöscht.");
  });
}

async function savePlan(day, meal, select, people) {
  await run(async () => {
    if (!select.value) {
      await api("/api/plans", { method: "DELETE", body: JSON.stringify({ day, meal }) });
    } else {
      await api("/api/plans", {
        method: "PUT",
        body: JSON.stringify({
          day,
          meal,
          recipe_id: Number(select.value),
          people: Number(people.value),
        }),
      });
    }
    await loadBoard();
    setNotice("Plan gespeichert.");
  });
}

async function clearPlan(day, meal) {
  await run(async () => {
    await api("/api/plans", { method: "DELETE", body: JSON.stringify({ day, meal }) });
    await loadBoard();
    setNotice("Eintrag geleert.");
  });
}

function reloadPlan() {
  run(() => loadBoard());
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Die Anfrage ist fehlgeschlagen.");
  }
  return payload;
}

async function run(action) {
  try {
    await action();
  } catch (error) {
    setNotice(error.message, true);
  }
}

function setNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
}

function formatQty(value) {
  return new Intl.NumberFormat("de-CH", { maximumFractionDigits: 2 }).format(Number(value));
}

function formatDay(iso) {
  const [year, month, day] = iso.split("-");
  return `${day}.${month}.${year}`;
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined) continue;
    if (key === "class") node.className = value;
    else if (key === "onclick") node.addEventListener("click", value);
    else node.setAttribute(key, value);
  }
  for (const child of children || []) {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
