<!-- זה החלק הרלוונטי בתוך admin_command.html -->
<!-- שים לב שזה חלק מתוך תבנית Jinja והוא דורש את הקוד מ־app.py תואם -->

{% for day in free_slots %}
<div class="border bg-white shadow-md rounded-xl p-4 my-2">
  <div class="flex justify-between items-center cursor-pointer toggle-day" data-day="{{ day }}">
    <div class="text-right font-bold text-lg text-gray-800">
      {{ weekdays[loop.index0 % 7] }} - {{ day }}
    </div>
    <button onclick="toggleAllSlots('{{ day }}')" class="bg-yellow-200 text-gray-700 px-2 py-1 text-sm rounded hover:bg-yellow-300 transition">
      כבה את כל היום
    </button>
  </div>

  <div class="mt-4 hidden day-slots" id="slots-{{ day }}">
    <div class="flex flex-wrap gap-4">
      {% for hour in free_slots[day] %}
      <div id="slot-{{ day }}-{{ hour.time }}"
        class="p-2 w-24 rounded-xl text-center text-sm font-bold relative
        {% if hour.enabled %} bg-green-100 text-green-900 {% else %} bg-gray-300 text-gray-600 {% endif %}">

        <div onclick="toggleActions('{{ day }}', '{{ hour.time }}')">
          {{ hour.time }}
        </div>

        <div id="actions-{{ day }}-{{ hour.time }}" class="hidden mt-1 space-y-1">
          {% if hour.enabled %}
            <button onclick="disableSlot('{{ day }}','{{ hour.time }}')" class="bg-yellow-200 text-gray-700 px-1 py-0.5 text-xs rounded hover:bg-yellow-300 w-full">כבה</button>
          {% else %}
            <button onclick="enableSlot('{{ day }}','{{ hour.time }}')" class="bg-green-200 text-green-700 px-1 py-0.5 text-xs rounded hover:bg-green-300 w-full">הפעל</button>
          {% endif %}
          <button onclick="editSlot('{{ day }}','{{ hour.time }}')" class="bg-blue-200 text-blue-700 px-1 py-0.5 text-xs rounded hover:bg-blue-300 w-full">ערוך</button>
          <button onclick="deleteSlot('{{ day }}','{{ hour.time }}')" class="bg-red-300 text-red-800 px-1 py-0.5 text-xs rounded hover:bg-red-400 w-full">מחק</button>
        </div>

      </div>
      {% endfor %}
      <button onclick="addSlot('{{ day }}')" class="bg-blue-600 text-white px-2 py-1 rounded text-sm hover:bg-blue-700">הוסף שעה</button>
    </div>
  </div>
</div>
{% endfor %}

<script>
  function toggleActions(day, time) {
    document.querySelectorAll('[id^="actions-"]').forEach(el => el.classList.add('hidden'));
    const actions = document.getElementById(`actions-${day}-${time}`);
    if (actions) actions.classList.toggle('hidden');
  }

  function toggleAllSlots(day) {
    const slotBox = document.getElementById(`slots-${day}`);
    if (slotBox) slotBox.classList.toggle('hidden');
  }

  async function enableSlot(day, time) {
    await fetch('/enable_slot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ day, time })
    });
    location.reload();
  }

  async function disableSlot(day, time) {
    await fetch('/disable_slot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ day, time })
    });
    location.reload();
  }

  async function deleteSlot(day, time) {
    await fetch('/delete_slot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ day, time })
    });
    location.reload();
  }

  async function editSlot(day, time) {
    const newTime = prompt("ערוך את השעה:", time);
    if (newTime && newTime !== time) {
      await fetch('/edit_slot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day, old_time: time, new_time: newTime })
      });
      location.reload();
    }
  }

  async function addSlot(day) {
    const time = prompt("הכנס שעה חדשה בפורמט HH:MM:");
    if (time) {
      await fetch('/add_slot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day, time })
      });
      location.reload();
    }
  }
</script>
