<template>
  <v-container>
    <v-snackbar
      v-model="connected"
      timeout="2000"
      color="success"
      content-class="text-center"
    >后台连接成功</v-snackbar>
    <v-row justify="center" align="center" dense>
      <v-col cols="3">
        <v-text-field label="回测天数" v-model="duration" />
      </v-col>
      <v-col cols="3">
        <v-file-input label="基金代码文件" v-model="codeListFile" />
      </v-col>
      <v-col cols="3" lg="2">
        <v-switch inset :label="forceUpdate ? '强制刷新' : '不强制刷新'" v-model="forceUpdate" />
      </v-col>
      <v-col cols="2" lg="1">
        <v-btn @click="process" :disabled="loading">提交</v-btn>
      </v-col>
    </v-row>
    <v-data-table
      :headers="header"
      :items="dataset"
      :loading="loading"
      multi-sort
      disable-pagination
      hide-default-footer
    ></v-data-table>
  </v-container>
</template>

<script>
import moment from "moment";
export const eel = window.eel;
eel.set_host("ws://localhost:9000");
// Expose the `sayHelloJS` function to Python as `say_hello_js`
function sayHelloJS(x) {
  console.log("Hello from " + x);
}
// WARN: must use window.eel to keep parse-able eel.expose{...}
window.eel.expose(sayHelloJS, "say_hello_js");
// Test calling sayHelloJS, then call the corresponding Python function
sayHelloJS("Javascript World!");
eel.say_hello_py("Javascript World!");
export default {
  name: "HelloWorld",
  data: function () {
    return {
      loading: false,
      codeListFile: null,
      codeListTxt: null,
      duration: 30,
      forceUpdate: false,
      todayString: moment().format("YYYY-MM-DD"),
      helloResponse: null,
      header: [],
      dataset: [],
    };
  },
  methods: {
    process: function () {
      var _this = this;
      this.loading = true;
      this.dataset = [];
      this.header = [];
      this.codeListTxt = null;
      if (!this.codeListFile) {
        this.getDataset();
      } else {
        let reader = new FileReader();
        reader.readAsText(this.codeListFile);
        reader.onload = (e) => {
          console.log(e.target.result);
          _this.codeListTxt = e.target.result.trim();
          _this.getDataset();
        };
        reader.onerror = (e) => {
          console.log(e);
          _this.loading = false;
        };
      }
    },
    async getDataset() {
      console.log([this.codeListTxt, this.forceUpdate, this.duration]);
      let result = await eel.process(
        this.codeListTxt,
        this.forceUpdate,
        this.duration
      )();
      // debugger; // eslint-disable-line
      console.log(result);
      for (let h of result["header"]) {
        this.header.push({ text: h, value: h });
      }
      this.header[this.header.length - 1]["sortable"] = true;
      this.header[this.header.length - 2]["sortable"] = true;
      this.dataset = result["dataset"];
      this.loading = false;
    },
  },
  computed: {
    numFunds: function () {
      return this.codeList.length;
    },
    connected: {
      get: function () {
        return this.helloResponse === "pong!";
      },
      set: function () {
        return;
      },
    },
  },
};
</script>