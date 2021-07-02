//
//  Generated file. Do not edit.
//

#import "GeneratedPluginRegistrant.h"

#if __has_include(<iamport_flutter/IamportFlutterPlugin.h>)
#import <iamport_flutter/IamportFlutterPlugin.h>
#else
@import iamport_flutter;
#endif

#if __has_include(<iamport_webview_flutter/FLTWebViewFlutterPlugin.h>)
#import <iamport_webview_flutter/FLTWebViewFlutterPlugin.h>
#else
@import iamport_webview_flutter;
#endif

#if __has_include(<uni_links/UniLinksPlugin.h>)
#import <uni_links/UniLinksPlugin.h>
#else
@import uni_links;
#endif

#if __has_include(<url_launcher/FLTURLLauncherPlugin.h>)
#import <url_launcher/FLTURLLauncherPlugin.h>
#else
@import url_launcher;
#endif

@implementation GeneratedPluginRegistrant

+ (void)registerWithRegistry:(NSObject<FlutterPluginRegistry>*)registry {
  [IamportFlutterPlugin registerWithRegistrar:[registry registrarForPlugin:@"IamportFlutterPlugin"]];
  [FLTWebViewFlutterPlugin registerWithRegistrar:[registry registrarForPlugin:@"FLTWebViewFlutterPlugin"]];
  [UniLinksPlugin registerWithRegistrar:[registry registrarForPlugin:@"UniLinksPlugin"]];
  [FLTURLLauncherPlugin registerWithRegistrar:[registry registrarForPlugin:@"FLTURLLauncherPlugin"]];
}

@end
