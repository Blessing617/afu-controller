package com.afu.controller

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.ViewModelProvider
import com.afu.controller.data.SettingsRepo
import com.afu.controller.ui.AppViewModel
import com.afu.controller.ui.GameOrchTheme
import com.afu.controller.ui.MainScreen

class MainActivity : ComponentActivity() {

    private val repo by lazy { SettingsRepo(applicationContext) }
    private val vm: AppViewModel by lazy {
        ViewModelProvider(this, AppViewModel.Factory(repo))[AppViewModel::class.java]
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            GameOrchTheme {
                MainScreen(vm)
            }
        }
    }

    // 退到后台就停掉画面刷新（省电省流量），回到前台再自动续上
    override fun onStart() {
        super.onStart()
        vm.resumeScreen()
    }

    override fun onStop() {
        vm.pauseScreen()
        super.onStop()
    }
}
