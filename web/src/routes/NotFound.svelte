<script lang="ts">
  import { navigate } from "../lib/router";
</script>

<div class="screen">
  <h1>Not found</h1>
  <p>Nothing lives at this address.</p>
  <button on:click={() => navigate("/")}>Go to join screen</button>
</div>
