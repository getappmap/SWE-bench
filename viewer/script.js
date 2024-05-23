import markdownit from "https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/+esm";

const dataContainer = document.getElementById("data-container");
const select = document.getElementById("instance_id");
const instances = {};

const markdown = markdownit();

const MD_FIELDS = ["original_issue", "problem_statement"];
const FIRST_FIELDS = ["model_patch", "patch", "text"];
const KNOWN_FIELDS = [...MD_FIELDS, ...FIRST_FIELDS];

// Function to update displayed data
function updateData(data) {
  dataContainer.innerHTML = "";
  for (const k of MD_FIELDS) addMdField(k, data);
  for (const k of FIRST_FIELDS) addPreField(k, data);
  for (const k in data) {
    if (!KNOWN_FIELDS.includes(k)) {
      addPreField(k, data);
    }
  }
}

function addPreField(k, data) {
  {
    const div = document.createElement("div");
    const h1 = document.createElement("h2");
    h1.textContent = k;
    div.appendChild(h1);
    const p = document.createElement("pre");
    p.textContent = stringify(data[k]);
    div.appendChild(p);
    dataContainer.appendChild(div);
  }
}

function addMdField(k, data) {
  {
    const div = document.createElement("div");
    const h1 = document.createElement("h2");
    h1.textContent = k;
    div.appendChild(h1);
    const p = document.createElement("section");
    if (data[k] === undefined) p.innerHTML = "<em>Not available</em>";
    else p.innerHTML = markdown.render(data[k]);
    div.appendChild(p);
    dataContainer.appendChild(div);
  }
}

function stringify(value) {
  switch (typeof value) {
    case "object":
      return JSON.stringify(value, undefined, 2);
    default:
      return String(value);
  }
}

select.addEventListener("change", (event) => {
  const selectedInstanceId = event.target.value;
  if (selectedInstanceId in instances) {
    updateData(instances[selectedInstanceId]);
  }
});

async function go() {
  const response = await fetch("data.jsonl");
  const data = await response.text();
  const lines = data.split("\n");
  for (const line of lines) {
    try {
      const json = JSON.parse(line);
      const instanceId = json.instance_id;
      instances[instanceId] = json;
    } catch {
      // Ignore invalid JSON lines
    }
  }

  // Populate select element with instance IDs (sorted)
  for (const instanceId of Object.keys(instances).sort()) {
    const option = document.createElement("option");
    option.value = instanceId;
    option.textContent = instanceId;
    select.appendChild(option);
  }

  // Select first instance by default
  if (select.options.length > 0) {
    select.value = select.options[0].value;
    updateData(instances[select.value]);
  }
}

go();

// Źródła:
// 1. https://medium.com/samsung-internet-dev/making-an-ar-game-with-aframe-529e03ae90cb
